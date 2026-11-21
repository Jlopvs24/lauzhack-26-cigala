"""Monthly state-transition engine, vectorised over paths with numpy.

One code path serves both modes:
- deterministic (one path per scenario, no randomness): central assumptions, no random shocks;
- Monte Carlo (n paths per scenario, fixed seed): random inflation, market returns,
  job losses and unexpected expenses.
Weather events apply to both.

Several scenarios ("blocks") can run in ONE pass: each block has its own
schedule and assumption values and reuses the SAME random draws (common random
numbers), so differences between blocks come from the assumptions, not from
noise. The sensitivity tornado uses this to evaluate every low/high variant at once.

Month t (0-based), for each path, in this order:
  1. investment return on opening investments:      R_t = I_t * (G_t - 1)
  2. interest on positive opening cash:             r_c * max(C_t, 0)
  3. cash flows: + income - income tax - living expenses - one-off costs
                 + one-off income - debt payments + new loans
  4. contribution: move min(planned, available cash) from cash to investments
  5. if cash < 0 and auto_liquidate: sell investments to cover it
  6. C_{t+1}, I_{t+1}; debt D_{t+1} from the amortisation schedule.

Identities checked on every run (see analysis.checks):
  C_{t+1} - C_t = income - tax - expenses - one_off_cost + one_off_income
                  - debt_payment + loan_proceeds + cash_interest - contribution + withdrawal
  NW_t = C_t + I_t - D_t
  NW_{t+1} - NW_t = income - tax - expenses - one_off_cost + one_off_income
                    - debt_interest + cash_interest + investment_return
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .schedule import DebtSchedule, Schedule, debt_schedule
from .weather import WeatherArrays

FLOW_KEYS = ("income", "income_tax", "living_expenses", "one_off_cost", "one_off_income",
             "debt_payment", "debt_interest", "loan_proceeds", "cash_interest",
             "investment_return", "contribution", "withdrawal")
# pillar 3a (#48 item 4): cash -> locked 3a account, its return, and (informational) the income tax it saved
PILLAR3A_KEYS = ("pillar_3a_contribution", "pillar_3a_return", "pillar_3a_tax_saving")
# informational payroll lines (#48 item 2): already deducted from `income`, not cash flows themselves
PAYROLL_KEYS = ("gross_income", "social_contributions", "bvg_employee", "bvg_employer")

PARAMS = ("inflation_mean", "inflation_sd", "real_wage_growth", "investment_return_mean",
          "investment_return_vol", "cash_interest_rate", "job_loss_annual_prob",
          "unemployment_mean_duration_months", "unemployment_replacement_rate",
          "unexpected_expense_annual_prob", "unexpected_expense_mean", "income_tax_scale",
          "auto_liquidate_investments", "pillar3a_max", "pillar3a_max_no_bvg", "pillar3a_no_bvg_share",
          "pillar3a_return", "payroll_bvg_entry")


@dataclass
class RunOutput:
    cash: np.ndarray          # (N, H+1)
    investments: np.ndarray   # (N, H+1)
    pillar_3a: np.ndarray     # (N, H+1) locked 3a balance: in net worth, not liquid (#48 item 4)
    debt: np.ndarray          # (H+1,) for a single scenario, (N, H+1) for a batch
    net_worth: np.ndarray     # (N, H+1)
    cpi: np.ndarray           # (N, H+1) price index, 1 at as_of
    flows: dict[str, np.ndarray] | None  # each (N, H), only when keep_flows
    unemployed_months: np.ndarray  # (N,) count
    debt_detail: DebtSchedule | None


def _monthly(rate_annual):
    return np.power(1.0 + np.asarray(rate_annual, dtype=float), 1.0 / 12.0)


def run(sched: Schedule, opening_cash: float, opening_investments: float, A: dict[str, float],
        tax_table: list[list[float]], weather: WeatherArrays, *, n_paths: int = 1,
        seed: int | None = None, stochastic: bool = False, keep_flows: bool = False) -> RunOutput:
    """Single scenario."""
    out = run_batch([sched], [A], opening_cash, opening_investments, tax_table, weather,
                    n_paths=n_paths, seed=seed, stochastic=stochastic, keep_flows=keep_flows)
    out.debt = out.debt[0]
    return out


def run_batch(scheds: list[Schedule], As: list[dict[str, float]], opening_cash: float,
              opening_investments: float, tax_table: list[list[float]],
              weather: WeatherArrays | list[WeatherArrays], *,
              n_paths: int = 1, seed: int | None = None, stochastic: bool = False,
              keep_flows: bool = False) -> RunOutput:
    """K scenarios in one pass. Block k = paths [k*n, (k+1)*n). All blocks share
    the same random draws. ``weather`` is shared by every case or given per case (a list
    of K), so e.g. the same plan under four named weathers runs in one pass.
    Returns arrays with N = K*n rows."""
    K = len(scheds)
    if K != len(As) or K == 0:
        raise ValueError("need one assumption dict per schedule")
    H = scheds[0].horizon
    n = n_paths if stochastic else 1
    N = K * n
    years = np.arange(H) // 12
    n_years = int(years[-1]) + 1

    def per_path(name: str) -> np.ndarray:   # (N,) value of a parameter for every path
        return np.repeat(np.array([float(a[name]) for a in As]), n)

    def stack(attr: str) -> np.ndarray:       # (N, H) planned amounts
        return np.repeat(np.stack([getattr(s, attr) for s in scheds]), n, axis=0)

    P = {k: per_path(k) for k in PARAMS}
    wl = weather if isinstance(weather, list) else [weather]
    if len(wl) not in (1, K):
        raise ValueError("need one weather, or one weather per schedule")

    def wx(attr: str) -> np.ndarray:          # (N, H) weather field for every path
        a = np.stack([getattr(w, attr) for w in wl])
        return np.repeat(a, n, axis=0) if len(wl) == K else np.broadcast_to(a, (N, H))

    W_infl, W_wage, W_shift = wx("inflation_override"), wx("real_wage_override"), wx("return_shift")
    W_shock, W_jl, W_unemp = wx("return_shock"), wx("job_loss_multiplier"), wx("forced_unemployment")
    income_plan = stack("income")
    expense_plan = np.repeat(np.stack([s.expenses for s in scheds]), n, axis=0)
    cost_plan = stack("one_off_cost")
    extra_plan = stack("one_off_income")
    contrib_plan = stack("investment_contribution")
    zeros_h = np.zeros(H)
    p3_plan = np.repeat(np.stack([s.pillar_3a if s.pillar_3a is not None else zeros_h for s in scheds]), n, axis=0)
    earned_plan = np.repeat(np.stack([np.where(s.gross > 0, s.gross, s.income) if s.gross is not None else s.income
                                      for s in scheds]), n, axis=0)  # for the 3a cap: gross if known
    cal_year = np.repeat(np.stack([s.calendar_year if s.calendar_year is not None else np.arange(H) // 12
                                   for s in scheds]), n, axis=0)
    p3_open = np.repeat(np.array([float(s.opening_pillar_3a) for s in scheds]), n)
    zeros = np.zeros(H)
    pay_plan = {k: np.repeat(np.stack([getattr(s, a) if getattr(s, a) is not None else zeros for s in scheds]), n, axis=0)
                for k, a in (("gross_income", "gross"), ("social_contributions", "social"),
                             ("bvg_employee", "bvg_employee"), ("bvg_employer", "bvg_employer"))}
    debts = [debt_schedule(s.liabilities, H) for s in scheds]
    d_pay = np.repeat(np.stack([d.payment for d in debts]), n, axis=0)
    d_int = np.repeat(np.stack([d.interest for d in debts]), n, axis=0)
    d_new = np.repeat(np.stack([d.proceeds for d in debts]), n, axis=0)
    d_bal = np.repeat(np.stack([d.balance for d in debts]), n, axis=0)

    # --- standard random draws for n base paths, shared by every block -------
    if stochastic:
        rng = np.random.default_rng(seed)
        z_infl = np.tile(rng.standard_normal((n, n_years)), (K, 1))
        z_ret = np.tile(rng.standard_normal((n, H)), (K, 1))
        u_hit = np.tile(rng.random((n, H)), (K, 1))
        u_size = np.tile(rng.random((n, H)), (K, 1))
        u_loss = np.tile(rng.random((n, H)), (K, 1))
        u_dur = np.tile(rng.random((n, H)), (K, 1))
    else:
        z_infl = np.zeros((N, n_years))
        z_ret = np.zeros((N, H))
        u_hit = np.ones((N, H))
        u_size = np.full((N, H), 0.5)
        u_loss = np.ones((N, H))
        u_dur = np.full((N, H), 0.5)

    # --- inflation (annual draws, constant within a year) -------------------
    pi_year = P["inflation_mean"][:, None] + P["inflation_sd"][:, None] * z_infl
    pi_year = np.clip(pi_year, -0.02, 0.12) if stochastic else pi_year
    pi_month = pi_year[:, years]                             # (N, H) annual rate in force
    wage_pi = pi_month.copy()                                # wages follow normal inflation
    pi_month = np.where(np.isnan(W_infl), pi_month, W_infl)
    cpi_factor = _monthly(pi_month)
    real_g = np.where(np.isnan(W_wage), P["real_wage_growth"][:, None], np.nan_to_num(W_wage))
    wage_factor = _monthly(wage_pi + real_g)
    cpi = np.ones((N, H + 1))
    cpi[:, 1:] = np.cumprod(cpi_factor, axis=1)
    wage_idx = np.ones((N, H + 1))
    wage_idx[:, 1:] = np.cumprod(wage_factor, axis=1)
    price_t = cpi[:, :H]          # amounts in month t are paid at the price level at the START of month t
    wage_t = wage_idx[:, :H]

    # --- investment returns ---------------------------------------------------
    mu = np.maximum(P["investment_return_mean"][:, None] + W_shift, -0.99)  # (N, H)
    s = P["investment_return_vol"][:, None] / np.sqrt(12.0)
    if stochastic:
        gross = np.exp(np.log1p(mu) / 12.0 - 0.5 * s * s + s * z_ret)
    else:
        gross = _monthly(mu)
    gross = gross * W_shock

    # --- unexpected expenses (exponential size by inverse transform) ---------
    hit = u_hit < (P["unexpected_expense_annual_prob"][:, None] / 12.0)
    unexpected = np.where(hit, -P["unexpected_expense_mean"][:, None] * np.log(np.maximum(u_size, 1e-300)), 0.0) * price_t

    # --- job loss: monthly hazard, geometric spell length by inverse transform -
    p_annual = np.clip(P["job_loss_annual_prob"], 0.0, 1.0)
    p_loss = (1.0 - (1.0 - p_annual) ** (1.0 / 12.0))[:, None] * W_jl  # (N, H)
    q = 1.0 / np.maximum(P["unemployment_mean_duration_months"], 1.0)
    with np.errstate(divide="ignore"):
        durations = np.where(q[:, None] >= 1.0, 1,
                             np.ceil(np.log(np.maximum(u_dur, 1e-300)) / np.log1p(-np.minimum(q, 1 - 1e-12))[:, None]))
    durations = np.maximum(durations, 1).astype(int)
    replacement = P["unemployment_replacement_rate"]

    tax_x = np.array([p[0] for p in tax_table], dtype=float)
    tax_y = np.array([p[1] for p in tax_table], dtype=float)
    # tax residence changes (#48 item 3): one table per (schedule, zone); None = one table for all
    zone_rows = None
    if any(s.tax_zone is not None for s in scheds):
        XS, YS, rows, seen = [], [], [], {}
        for s in scheds:  # tables are shared across cases: index each distinct table once
            tabs = s.tax_tables if s.tax_zone is not None else [tax_table]
            z = s.tax_zone if s.tax_zone is not None else np.zeros(H, dtype=int)
            idx = []
            for tb in tabs:
                key = tuple(map(tuple, tb))
                if key not in seen:
                    seen[key] = len(XS)
                    XS.append(np.array([p[0] for p in tb], dtype=float))
                    YS.append(np.array([p[1] for p in tb], dtype=float))
                idx.append(seen[key])
            rows.append(np.asarray(idx)[z])
        zone_rows = np.repeat(np.stack(rows), n, axis=0)  # (N, H) global table index
        zones_at = [np.unique(zone_rows[:, t]) for t in range(H)]
    tax_scale = P["income_tax_scale"]
    r_cash = _monthly(P["cash_interest_rate"]) - 1.0
    auto_liq = P["auto_liquidate_investments"] >= 0.5

    cash = np.empty((N, H + 1))
    inv = np.empty((N, H + 1))
    cash[:, 0] = opening_cash
    inv[:, 0] = opening_investments
    flows = {k: np.zeros((N, H)) for k in FLOW_KEYS + PAYROLL_KEYS + PILLAR3A_KEYS} if keep_flows else None
    p3 = np.empty((N, H + 1))
    p3[:, 0] = p3_open
    g3 = _monthly(P["pillar3a_return"])
    paid_year = np.zeros(N)
    any_3a = bool(p3_plan.any())
    remaining = np.zeros(N, dtype=int)
    unemployed_count = np.zeros(N, dtype=int)

    for t in range(H):
        C, I = cash[:, t], inv[:, t]
        planned_income = income_plan[:, t]
        employed = planned_income > 0
        new_loss = employed & (remaining == 0) & (u_loss[:, t] < p_loss[:, t])
        remaining = np.where(new_loss, durations[:, t], remaining)
        unemployed = employed & ((remaining > 0) | W_unemp[:, t])
        remaining = np.where(employed, np.maximum(remaining - 1, 0), remaining)
        unemployed_count += unemployed
        emp = np.where(unemployed, replacement, 1.0)

        income = planned_income * emp * wage_t[:, t]
        # tax rate looked up on annualised income at today's prices (no bracket creep)
        annual = 12.0 * planned_income * emp

        def tax_rate(x):
            if zone_rows is None:
                return np.interp(x, tax_x, tax_y)
            zt = zone_rows[:, t]
            if len(zones_at[t]) == 1:
                z = zones_at[t][0]
                return np.interp(x, XS[z], YS[z])
            r = np.empty(N)
            for z in zones_at[t]:
                m = zt == z
                r[m] = np.interp(x[m], XS[z], YS[z])
            return r

        tax = tax_rate(annual) * tax_scale * income
        living = expense_plan[:, t] * price_t[:, t]
        cost = cost_plan[:, t] * price_t[:, t] + unexpected[:, t]
        extra = extra_plan[:, t] * price_t[:, t]
        inv_ret = I * (gross[:, t] - 1.0)
        c_int = np.maximum(C, 0.0) * r_cash

        pre = C + income - tax - living - cost + extra - d_pay[:, t] + d_new[:, t] + c_int
        # pillar 3a first (when cash allows, up to what is left of this calendar year's cap); the
        # payment is deducted from taxable income, so the month's tax is recomputed on net - 3a
        c3 = saving = 0.0
        if any_3a:
            if t > 0:
                paid_year = np.where(cal_year[:, t] != cal_year[:, t - 1], 0.0, paid_year)
            earned = 12.0 * earned_plan[:, t]  # today's prices; the caps are not indexed
            cap = np.where(earned >= P["payroll_bvg_entry"], P["pillar3a_max"],
                           np.minimum(P["pillar3a_no_bvg_share"] * earned, P["pillar3a_max_no_bvg"]))
            room = np.where(planned_income > 0, np.maximum(cap - paid_year, 0.0), 0.0)
            c3 = np.minimum(np.minimum(p3_plan[:, t] * price_t[:, t], room), np.maximum(pre, 0.0))
            if c3.any():
                deducted = annual - 12.0 * c3 / wage_t[:, t]
                tax_3a = tax_rate(np.maximum(deducted, 0.0)) * tax_scale * np.maximum(income - c3, 0.0)
                saving = np.where(c3 > 0, tax - tax_3a, 0.0)
                tax = tax - saving
                pre = pre + saving - c3
                paid_year = paid_year + c3
        ret3 = p3[:, t] * (g3 - 1.0)
        p3[:, t + 1] = p3[:, t] + ret3 + c3
        contrib = np.clip(pre, 0.0, contrib_plan[:, t] * price_t[:, t])
        i_mid = I + inv_ret + contrib
        after = pre - contrib
        withdraw = np.where(auto_liq, np.minimum(np.maximum(-after, 0.0), np.maximum(i_mid, 0.0)), 0.0)
        cash[:, t + 1] = after + withdraw
        inv[:, t + 1] = i_mid - withdraw

        if flows is not None:
            flows["income"][:, t] = income
            flows["income_tax"][:, t] = tax
            flows["living_expenses"][:, t] = living
            flows["one_off_cost"][:, t] = cost
            flows["one_off_income"][:, t] = extra
            flows["debt_payment"][:, t] = d_pay[:, t]
            flows["debt_interest"][:, t] = d_int[:, t]
            flows["loan_proceeds"][:, t] = d_new[:, t]
            flows["cash_interest"][:, t] = c_int
            flows["investment_return"][:, t] = inv_ret
            flows["contribution"][:, t] = contrib
            flows["withdrawal"][:, t] = withdraw
            flows["pillar_3a_contribution"][:, t] = c3
            flows["pillar_3a_return"][:, t] = ret3
            flows["pillar_3a_tax_saving"][:, t] = saving
            on_pay = np.where(unemployed, 0.0, 1.0) * wage_t[:, t]  # no payslip while unemployed
            for k, plan in pay_plan.items():
                flows[k][:, t] = plan[:, t] * on_pay

    net_worth = cash + inv + p3 - d_bal
    return RunOutput(cash=cash, investments=inv, pillar_3a=p3, debt=d_bal, net_worth=net_worth, cpi=cpi,
                     flows=flows, unemployed_months=unemployed_count,
                     debt_detail=debts[0] if K == 1 else None)
