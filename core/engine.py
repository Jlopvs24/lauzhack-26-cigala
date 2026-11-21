"""Monthly state-transition engine, vectorised over paths with numpy.

One code path serves both modes:
- deterministic (n_paths=1, no randomness): central assumptions, no random shocks;
- Monte Carlo (n_paths=N, fixed seed): random inflation, market returns,
  job losses and unexpected expenses.
Weather events apply to both.

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


@dataclass
class RunOutput:
    cash: np.ndarray          # (N, H+1)
    investments: np.ndarray   # (N, H+1)
    debt: np.ndarray          # (H+1,)  deterministic schedule (fixed-rate loans)
    net_worth: np.ndarray     # (N, H+1)
    cpi: np.ndarray           # (N, H+1) price index, 1 at as_of
    flows: dict[str, np.ndarray] | None  # each (N, H), only when keep_flows
    unemployed_months: np.ndarray  # (N,) count
    debt_detail: DebtSchedule


def _monthly(rate_annual: np.ndarray | float) -> np.ndarray | float:
    return np.power(1.0 + np.asarray(rate_annual, dtype=float), 1.0 / 12.0)


def run(sched: Schedule, opening_cash: float, opening_investments: float, A: dict[str, float],
        tax_table: list[list[float]], weather: WeatherArrays, *, n_paths: int = 1,
        seed: int | None = None, stochastic: bool = False, keep_flows: bool = False) -> RunOutput:
    H = sched.horizon
    N = n_paths if stochastic else 1
    rng = np.random.default_rng(seed)
    years = np.arange(H) // 12
    n_years = int(years[-1]) + 1

    # --- inflation (annual draws, constant within a year) -------------------
    if stochastic and A["inflation_sd"] > 0:
        pi_year = rng.normal(A["inflation_mean"], A["inflation_sd"], size=(N, n_years))
        pi_year = np.clip(pi_year, -0.02, 0.12)
    else:
        pi_year = np.full((N, n_years), A["inflation_mean"])
    pi_month = pi_year[:, years]                              # (N, H) annual rate in force
    wage_pi = pi_month.copy()                                # wages follow normal inflation
    has_override = ~np.isnan(weather.inflation_override)
    pi_month[:, has_override] = weather.inflation_override[has_override]
    cpi_factor = _monthly(pi_month)
    real_g = np.where(np.isnan(weather.real_wage_override), A["real_wage_growth"], weather.real_wage_override)
    wage_factor = _monthly(wage_pi + real_g[None, :])
    cpi = np.ones((N, H + 1))
    cpi[:, 1:] = np.cumprod(cpi_factor, axis=1)
    wage_idx = np.ones((N, H + 1))
    wage_idx[:, 1:] = np.cumprod(wage_factor, axis=1)
    # amounts in month t are paid at the price level reached at the START of month t
    price_t = cpi[:, :H]
    wage_t = wage_idx[:, :H]

    # --- investment returns ---------------------------------------------------
    mu = A["investment_return_mean"] + weather.return_shift            # (H,)
    if stochastic and A["investment_return_vol"] > 0:
        s = A["investment_return_vol"] / np.sqrt(12.0)
        m = np.log1p(np.maximum(mu, -0.99)) / 12.0 - 0.5 * s * s
        gross = np.exp(rng.normal(m[None, :], s, size=(N, H)))
    else:
        gross = np.broadcast_to(_monthly(np.maximum(mu, -0.99)), (N, H)).copy()
    gross *= weather.return_shock[None, :]

    # --- unexpected expenses --------------------------------------------------
    if stochastic and A["unexpected_expense_annual_prob"] > 0 and A["unexpected_expense_mean"] > 0:
        hit = rng.random((N, H)) < A["unexpected_expense_annual_prob"] / 12.0
        unexpected = hit * rng.exponential(A["unexpected_expense_mean"], size=(N, H)) * price_t
    else:
        unexpected = np.zeros((N, H))

    # --- job loss draws (consumed inside the loop) ---------------------------
    p_loss = 1.0 - (1.0 - min(max(A["job_loss_annual_prob"], 0.0), 1.0)) ** (1.0 / 12.0)
    loss_u = rng.random((N, H)) if stochastic else np.ones((N, H))
    mean_dur = max(A["unemployment_mean_duration_months"], 1.0)
    durations = rng.geometric(1.0 / mean_dur, size=(N, H)) if stochastic else np.ones((N, H), dtype=int)
    replacement = A["unemployment_replacement_rate"]

    debt = debt_schedule(sched.liabilities, H)
    tax_x = np.array([p[0] for p in tax_table], dtype=float)
    tax_y = np.array([p[1] for p in tax_table], dtype=float) * A["income_tax_scale"]
    r_cash = _monthly(A["cash_interest_rate"]) - 1.0
    auto_liq = A["auto_liquidate_investments"] >= 0.5

    cash = np.empty((N, H + 1))
    inv = np.empty((N, H + 1))
    cash[:, 0] = opening_cash
    inv[:, 0] = opening_investments
    flows = {k: np.zeros((N, H)) for k in FLOW_KEYS} if keep_flows else None
    remaining = np.zeros(N, dtype=int)
    unemployed_count = np.zeros(N, dtype=int)

    for t in range(H):
        C, I = cash[:, t], inv[:, t]
        planned_income = sched.income[t]
        if planned_income > 0:
            new_loss = (remaining == 0) & (loss_u[:, t] < p_loss * weather.job_loss_multiplier[t])
            remaining = np.where(new_loss, durations[:, t], remaining)
            unemployed = (remaining > 0) | weather.forced_unemployment[t]
            remaining = np.maximum(remaining - 1, 0)
        else:
            unemployed = np.zeros(N, dtype=bool)
        unemployed_count += unemployed
        emp = np.where(unemployed, replacement, 1.0)

        income = planned_income * emp * wage_t[:, t]
        # tax rate looked up on annualised income at today's prices (no bracket creep)
        rate = np.interp(12.0 * planned_income * emp, tax_x, tax_y)
        tax = rate * income
        living = sched.expenses[t] * price_t[:, t]
        cost = sched.one_off_cost[t] * price_t[:, t] + unexpected[:, t]
        extra = sched.one_off_income[t] * price_t[:, t]
        inv_ret = I * (gross[:, t] - 1.0)
        c_int = np.maximum(C, 0.0) * r_cash

        pre = (C + income - tax - living - cost + extra - debt.payment[t] + debt.proceeds[t] + c_int)
        planned_contrib = sched.investment_contribution[t] * price_t[:, t]
        contrib = np.clip(pre, 0.0, planned_contrib)
        i_mid = I + inv_ret + contrib
        after = pre - contrib
        withdraw = np.minimum(np.maximum(-after, 0.0), np.maximum(i_mid, 0.0)) if auto_liq else np.zeros(N)
        cash[:, t + 1] = after + withdraw
        inv[:, t + 1] = i_mid - withdraw

        if flows is not None:
            flows["income"][:, t] = income
            flows["income_tax"][:, t] = tax
            flows["living_expenses"][:, t] = living
            flows["one_off_cost"][:, t] = cost
            flows["one_off_income"][:, t] = extra
            flows["debt_payment"][:, t] = debt.payment[t]
            flows["debt_interest"][:, t] = debt.interest[t]
            flows["loan_proceeds"][:, t] = debt.proceeds[t]
            flows["cash_interest"][:, t] = c_int
            flows["investment_return"][:, t] = inv_ret
            flows["contribution"][:, t] = contrib
            flows["withdrawal"][:, t] = withdraw

    net_worth = cash + inv - debt.balance[None, :]
    return RunOutput(cash=cash, investments=inv, debt=debt.balance, net_worth=net_worth, cpi=cpi,
                     flows=flows, unemployed_months=unemployed_count, debt_detail=debt)
