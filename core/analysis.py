"""Metrics, goals, financial health, accounting checks and sensitivity."""
from __future__ import annotations

import numpy as np

from .engine import RunOutput
from .models import Profile

PRIORITY_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}
HEALTH_WEIGHTS = {"liquidity": 0.3, "debt": 0.2, "goals": 0.3, "resilience": 0.2}
TOL = 0.01  # CHF


def r2(x) -> float:
    return round(float(x), 2)


def series(a: np.ndarray) -> list[float]:
    return [round(float(v), 2) for v in a]


def first_negative(cash_row: np.ndarray) -> int | None:
    """0-based month whose END cash is negative (cash_row has H+1 points)."""
    idx = np.nonzero(cash_row[1:] < -TOL)[0]
    return int(idx[0]) if idx.size else None


def goal_value(out: RunOutput, goal_metric: str, k: int) -> np.ndarray:
    liquid = out.cash[:, k] + out.investments[:, k]
    return liquid - out.debt[k] if goal_metric == "net_worth" else liquid


def evaluate_goals(profile: Profile, det: RunOutput, mc: RunOutput | None) -> list[dict]:
    res = []
    for g in profile.goals:
        k = g.target_month + 1  # balance at END of target month
        dv = float(goal_value(det, g.metric, k)[0])
        mv = goal_value(mc, g.metric, k) if mc is not None else None
        liquid_det = det.cash[0, 1:] + det.investments[0, 1:] - (det.debt[1:] if g.metric == "net_worth" else 0)
        reached = np.nonzero(liquid_det >= g.target)[0]
        res.append({
            "name": g.name, "target": r2(g.target), "target_month": g.target_month, "priority": g.priority,
            "metric": g.metric,
            "deterministic_value": r2(dv), "met_deterministic": bool(dv >= g.target),
            "first_reached_month_deterministic": int(reached[0]) if reached.size else None,
            "probability": round(float(np.mean(mv >= g.target)), 3) if mv is not None else None,
            "p50_value": r2(np.percentile(mv, 50)) if mv is not None else None,
        })
    return res


def bands(arr: np.ndarray) -> dict[str, list[float]]:
    p = np.percentile(arr, [10, 50, 90], axis=0)
    return {"p10": series(p[0]), "p50": series(p[1]), "p90": series(p[2])}


def health(det: RunOutput, mc: RunOutput | None, goals: list[dict], A: dict[str, float],
           resilience: dict | None = None) -> dict:
    f = det.flows
    living = f["living_expenses"][0]
    liquid = det.cash[0, 1:] + det.investments[0, 1:]
    months_cover = np.where(living > 0, liquid / np.maximum(living, 1e-9), np.inf)
    worst_idx = int(np.argmin(months_cover))
    worst = float(months_cover[worst_idx])
    now = float((det.cash[0, 0] + det.investments[0, 0]) / living[0]) if living[0] > 0 else float("inf")
    target = max(A["liquidity_target_months"], 1e-9)
    liq_score = float(np.clip(worst / target, 0.0, 1.0))

    income = f["income"][0]
    pay = f["debt_payment"][0]
    with np.errstate(divide="ignore", invalid="ignore"):
        dsr = np.where(income > 0, pay / income, np.where(pay > 0, np.inf, 0.0))
    max_dsr = float(np.max(dsr))
    limit = A["debt_service_limit"]
    # pass/fail with margin: any debt within the limit scores 1, so a loan that closes a gap never looks worse
    debt_score = (1.0 if max_dsr <= limit else float(np.clip(1.0 - (max_dsr - limit) / limit, 0.0, 1.0))) \
        if np.isfinite(max_dsr) else 0.0

    min_cash = (mc if mc is not None else det).cash[:, 1:].min(axis=1)
    p_short = float(np.mean(min_cash < -TOL))

    comps = {
        "liquidity": {
            "score": round(liq_score, 3), "value": _fin(worst), "unit": "months of expenses at the tightest month",
            "worst_month": worst_idx, "today_value": _fin(now),
            "explanation": (f"At the tightest point (month {worst_idx + 1}) cash plus investments cover "
                            f"{_fmt_months(worst)} of living expenses" if worst >= 0 else
                            f"At the tightest point (month {worst_idx + 1}) the plan is short by "
                            f"{_fmt_months(-worst)} of living expenses (unfunded)")
                           + f"; {A['liquidity_target_months']:g} months counts as healthy.",
        },
        "debt": {
            "score": round(debt_score, 3), "value": _fin(max_dsr), "unit": "max debt payments / income",
            "passed": bool(max_dsr <= limit), "limit": limit,
            "margin": _fin(limit - max_dsr),
            "explanation": ("No debt payments." if max_dsr == 0 else
                            f"Debt payments reach {_pct(max_dsr)} of income at most: "
                            + ("within" if max_dsr <= limit else "above") + f" the {_pct(limit)} limit."),
        },
        "resilience": ({
            "score": round(1.0 - p_short, 3), "value": round(p_short, 3),
            "unit": "share of simulated paths where cash goes negative",
            "explanation": f"Under these assumptions, cash runs out in {_pct(p_short)} of {mc.cash.shape[0]} simulated paths.",
        } if mc is not None or not resilience or not resilience["of"] else {
            "score": round(resilience["holds_in"] / resilience["of"], 3), "value": resilience["holds_in"],
            "unit": f"named weather scenarios (of {resilience['of']}) in which the plan holds",
            "explanation": (f"Under these assumptions the plan holds ({resilience['holds_means']}) in "
                            f"{resilience['holds_in']} of {resilience['of']} weather scenarios: " + ", ".join(
                                f"{r['type'].replace('_', ' ')} {'holds' if r['holds'] else 'breaks'}"
                                for r in resilience["by_weather"] if r["holds"] is not None) + "."),
        }),
    }
    if goals:
        wsum = sum(PRIORITY_WEIGHT.get(g["priority"], 1.0) for g in goals)
        gp = sum(PRIORITY_WEIGHT.get(g["priority"], 1.0) *
                 (g["probability"] if mc is not None else g["met_deterministic"]) for g in goals) / wsum
        comps["goals"] = {
            "score": round(gp, 3), "value": round(gp, 3),
            "unit": "priority-weighted share of simulated goals met" if mc is not None else "priority-weighted share of deterministic goals met",
            "explanation": "Under these assumptions: " + "; ".join(
                f"{g['name']}: {_pct(g['probability'])} of simulated paths" if mc is not None else
                f"{g['name']}: {'met' if g['met_deterministic'] else 'not met'}" for g in goals),
        }
    weights = {k: w for k, w in HEALTH_WEIGHTS.items() if k in comps}
    total = sum(weights.values())
    score = 100.0 * sum(comps[k]["score"] * w for k, w in weights.items()) / total
    for k in comps:
        comps[k]["weight"] = round(weights[k] / total, 3)
    level = "strong" if score >= 70 else "ok" if score >= 40 else "fragile"
    return {"score": round(score, 1), "level": level, "components": comps,
            "method": "Weighted average of component scores (0-1) x 100. Weights are a value judgement and shown openly."}


def _fin(x: float):
    return None if not np.isfinite(x) else round(float(x), 2)


def _fmt_months(x: float) -> str:
    return "unlimited months" if not np.isfinite(x) else f"{x:.1f} months"


def _pct(x: float) -> str:
    return "n/a" if not np.isfinite(x) else f"{100 * x:.0f}%"


def checks(det: RunOutput, mc: RunOutput, used_assumptions: list[dict]) -> list[dict]:
    f = {k: v[0] for k, v in det.flows.items()}
    c, i, d = det.cash[0], det.investments[0], det.debt
    cash_resid = np.diff(c) - (f["income"] - f["income_tax"] - f["living_expenses"] - f["one_off_cost"]
                               + f["one_off_income"] - f["debt_payment"] + f["loan_proceeds"]
                               + f["cash_interest"] - f["contribution"] + f["withdrawal"])
    nw = det.net_worth[0]
    nw_resid = np.diff(nw) - (f["income"] - f["income_tax"] - f["living_expenses"] - f["one_off_cost"]
                              + f["one_off_income"] - f["debt_interest"] + f["cash_interest"] + f["investment_return"])
    bs_resid = nw - (c + i - d)
    inv_resid = np.diff(i) - (f["investment_return"] + f["contribution"] - f["withdrawal"])
    p = np.percentile(mc.net_worth, [10, 50, 90], axis=0)
    out = [
        _chk("cash_flow_identity", np.max(np.abs(cash_resid)),
             "Closing cash = opening cash + all cash flows, every month"),
        _chk("net_worth_change_identity", np.max(np.abs(nw_resid)),
             "Change in net worth = income - tax - expenses - interest + returns (transfers cancel out)"),
        _chk("balance_sheet_identity", np.max(np.abs(bs_resid)), "Net worth = cash + investments - debt"),
        _chk("investment_account_identity", np.max(np.abs(inv_resid)),
             "Investments move only by returns, contributions and withdrawals"),
        {"name": "debt_never_negative", "passed": bool(np.min(d) >= -TOL), "detail": f"min debt {np.min(d):.2f}"},
        {"name": "investments_never_negative", "passed": bool(np.min(mc.investments) >= -TOL and np.min(i) >= -TOL),
         "detail": f"min investments {min(np.min(mc.investments), np.min(i)):.2f}"},
        {"name": "bands_ordered", "passed": bool(np.all(p[0] <= p[1] + TOL) and np.all(p[1] <= p[2] + TOL)),
         "detail": "p10 <= p50 <= p90 at every month"},
        {"name": "assumptions_sourced", "passed": all(bool(a.get("source")) for a in used_assumptions),
         "detail": f"{len(used_assumptions)} assumptions, each with a source and kind"},
    ]
    return out


def _chk(name: str, resid: float, detail: str) -> dict:
    return {"name": name, "passed": bool(resid <= TOL), "max_abs_error": round(float(resid), 6), "detail": detail}
