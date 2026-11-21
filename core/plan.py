"""Plan check (#27): constraints, feasibility first, deterministic resilience, branch headlines.

Everything here reads the deterministic path. A plan is judged by whether it holds
(no unfunded gap, debt within the limit, goals met) before any score; the score
stays secondary and its weights visible.
"""
from __future__ import annotations

import numpy as np

from .analysis import PRIORITY_WEIGHT, TOL, first_negative, r2
from .engine import run_batch
from .weather import build_weather

WEATHER_TYPES = ("recession", "inflation", "market_crash", "job_loss")


def _months_in(mask: np.ndarray) -> tuple[int | None, int]:
    idx = np.flatnonzero(mask)
    return (int(idx[0]) if idx.size else None), int(idx.size)


def _assumption_id(aset, param: str) -> str | None:
    try:
        return aset.get(param)["id"]
    except KeyError:
        return None


def constraints(det, A: dict, goals: list[dict], aset) -> list[dict]:
    """Every constraint the plan is checked against, with threshold, margin and breaches."""
    f = det.flows
    cash = det.cash[0, 1:]
    out = []
    first, n = _months_in(cash < -TOL)
    out.append({
        "name": "no_funding_gap", "label": "Cash never goes negative (no unfunded financing need)",
        "kind": "hard", "defined_by": "engine", "source": "UBS starter-kit convention: negative cash is an unfunded need",
        "threshold": 0.0, "unit": "CHF", "value": r2(cash.min()), "margin": r2(cash.min()),
        "passed": first is None, "first_breach_month": first, "months_in_breach": n,
    })

    income, pay = f["income"][0], f["debt_payment"][0]
    with np.errstate(divide="ignore", invalid="ignore"):
        dsr = np.where(income > 0, pay / income, np.where(pay > 0, np.inf, 0.0))
    limit = A["debt_service_limit"]
    first, n = _months_in(dsr > limit + 1e-12)
    max_dsr = float(dsr.max())
    out.append({
        "name": "debt_service_limit", "label": "Debt payments stay within the limit of income",
        "kind": "hard", "defined_by": "assumption", "source": _assumption_id(aset, "debt_service_limit"),
        "threshold": limit, "unit": "debt payments / income", "value": None if not np.isfinite(max_dsr) else round(max_dsr, 4),
        "margin": None if not np.isfinite(max_dsr) else round(limit - max_dsr, 4),
        "passed": first is None, "first_breach_month": first, "months_in_breach": n,
    })

    living = f["living_expenses"][0]
    liquid = cash + det.investments[0, 1:]
    cover = np.where(living > 0, liquid / np.maximum(living, 1e-9), np.inf)
    target = A["liquidity_target_months"]
    first, n = _months_in(cover < target)
    worst = float(cover.min())
    out.append({
        "name": "liquidity_buffer", "label": f"Cash plus investments cover {target:g} months of living costs",
        "kind": "target", "defined_by": "assumption", "source": _assumption_id(aset, "liquidity_target_months"),
        "threshold": target, "unit": "months of living costs", "value": r2(worst) if np.isfinite(worst) else None,
        "margin": r2(worst - target) if np.isfinite(worst) else None,
        "passed": first is None, "first_breach_month": first, "months_in_breach": n,
    })

    for g in goals:
        margin = g["deterministic_value"] - g["target"]
        out.append({
            "name": f"goal:{g['name']}", "label": f"{g['name']}: CHF {g['target']:,.0f} by month {g['target_month'] + 1}",
            "kind": "goal", "defined_by": "user", "source": "profile goal", "priority": g["priority"],
            "threshold": g["target"], "unit": "CHF", "value": g["deterministic_value"], "margin": r2(margin),
            "passed": bool(g["met_deterministic"]), "first_breach_month": None if g["met_deterministic"] else g["target_month"],
            "months_in_breach": None,
        })
    return out


def weather_resilience(profile, sched, A, aset, weather, goals) -> dict:
    """The same plan under each named weather scenario, deterministically (no random draws)."""
    H = profile.horizon_months
    given = [{"type": w} if isinstance(w, str) else dict(w) for w in weather or []]
    current = {w.get("type") for w in given}
    rows, kinds, ws = [], [], []
    for kind in WEATHER_TYPES:
        try:
            ws.append(build_weather(given + ([] if kind in current else [{"type": kind}]), H))
            kinds.append(kind)
        except ValueError:  # e.g. its default start month lies beyond a short horizon
            rows.append({"type": kind, "already_applied": False, "holds": None, "status": "outside_horizon"})
    out = (run_batch([sched] * len(ws), [A] * len(ws), profile.cash, profile.investments, profile.tax_table(aset), ws,
                     stochastic=False) if ws else None)  # all named weathers in one pass
    for j, kind in enumerate(kinds):
        missed = []
        for g in goals:
            k = g["target_month"] + 1
            v = out.cash[j, k] + out.investments[j, k] + (
                out.pillar_3a[j, k] - out.debt[j, k] if g["metric"] == "net_worth" else 0)
            if v < g["target"]:
                missed.append(g["name"])
        gap = first_negative(out.cash[j])
        rows.append({"type": kind, "already_applied": kind in current, "holds": gap is None and not missed,
                     "first_negative_month": gap, "min_cash": r2(out.cash[j, 1:].min()),
                     "final_net_worth": r2(out.net_worth[j, -1]), "missed_goals": missed})
    rows.sort(key=lambda r: WEATHER_TYPES.index(r["type"]))
    tested = [r for r in rows if r["holds"] is not None]
    return {"holds_in": sum(r["holds"] for r in tested), "of": len(tested), "by_weather": rows,
            "holds_means": "no funding gap and every dated goal met"}


def plan_level(cons: list[dict]) -> str:
    """needs_financing > infeasible > holds_below_target > holds (the first that applies)."""
    by = {c["name"]: c for c in cons}
    if not by["no_funding_gap"]["passed"]:
        return "needs_financing"
    if any(not c["passed"] for c in cons if c["kind"] in ("hard", "goal")):
        return "infeasible"
    if any(not c["passed"] for c in cons if c["kind"] == "target"):
        return "holds_below_target"
    return "holds"


def plan_check(cons: list[dict], resilience: dict, health: dict, exploration: dict | None = None) -> dict:
    by = {c["name"]: c for c in cons}
    gap = by["no_funding_gap"]
    failed_hard = [c for c in cons if c["kind"] == "hard" and not c["passed"]]
    failed_goals = [c for c in cons if c["kind"] == "goal" and not c["passed"]]
    failed_targets = [c for c in cons if c["kind"] == "target" and not c["passed"]]
    if not gap["passed"]:
        level, label = "needs_financing", (f"Needs financing: funding gap of CHF {abs(gap['value']):,.0f} "
                                           f"from month {gap['first_breach_month'] + 1}")
    elif failed_hard or failed_goals:
        level = "infeasible"
        label = "Does not hold: " + "; ".join(c["label"] for c in failed_hard + failed_goals)
    elif failed_targets:
        level, label = "holds_below_target", "Holds, below target: " + "; ".join(c["label"] for c in failed_targets)
    else:
        level, label = "holds", "Holds: no funding gap, debt within the limit, goals met"
    rs = (exploration or {}).get("reverse_stress") or {}
    shock = rs.get("value") if rs.get("status") == "threshold_found" else (0.0 if rs.get("status") == "already_broken" else None)
    return {
        "level": level, "feasible": level in ("holds", "holds_below_target"), "label": label,
        "failed": [c["name"] for c in failed_hard + failed_goals + failed_targets],
        "resilience": {"holds_in_weather": resilience["holds_in"], "of": resilience["of"],
                       "shock_buffer_chf": shock, "shock_buffer_status": rs.get("status"),
                       "shock_buffer_means": "smallest extra one-off cost in month 0 that breaks the plan"},
        "score": health["score"], "score_is_secondary": True, "score_method": health["method"],
        "condition": "Under these assumptions; not a forecast and not advice.",
    }


# --- branch card headline ----------------------------------------------------------

def slot_a(metrics: dict, goals: list[dict], health: dict) -> dict:
    """Does it hold? First that applies: funding gap, a missed goal, else the tightest buffer."""
    if metrics["first_negative_month"] is not None:
        gap = abs(metrics["min_cash"])
        return {"kind": "funding_gap", "value": r2(gap), "month": metrics["first_negative_month"],
                "text": f"Funding gap CHF {gap:,.0f} from month {metrics['first_negative_month'] + 1}"}
    missed = [g for g in goals if not g["met_deterministic"]]
    if missed:
        g = sorted(missed, key=lambda g: (-PRIORITY_WEIGHT.get(g["priority"], 1.0), g["target_month"]))[0]
        short = g["target"] - g["deterministic_value"]
        return {"kind": "goal_missed", "goal": g["name"], "value": r2(short), "month": g["target_month"],
                "text": f"{g['name']} missed by CHF {short:,.0f}"}
    liq = health["components"]["liquidity"]
    if liq["value"] is None:  # no living costs: cover is unbounded
        return {"kind": "tightest_buffer", "value": None, "month": None, "text": "No living costs to cover"}
    return {"kind": "tightest_buffer", "value": liq["value"], "month": liq["worst_month"],
            "text": f"Tightest buffer: {liq['value']:.1f} months (month {liq['worst_month'] + 1})"}


# differences smaller than this are not worth a headline (the normalised gap alone is scale-free)
MATERIAL = {"CHF": 1000.0, "months": 0.5, "month": 3}
SLOT_B = {  # key: (label, unit, higher_is_better)
    "final_net_worth_real": ("Net worth after 10 years (today's prices)", "CHF", True),
    "min_cash": ("Lowest cash", "CHF", True),
    "liquidity_months": ("Tightest buffer", "months", True),
    "final_debt": ("Debt left at the end", "CHF", False),
    "earliest_goal_month": ("First goal reached (net of debt)", "month", False),
}


def slot_b_values(result: dict) -> dict:
    m = result["metrics"]
    d = result["deterministic"]
    # net of debt: borrowed cash must not count as reaching a savings goal
    own = [c + i - b for c, i, b in zip(d["cash"][1:], d["investments"][1:], d["debt"][1:])]
    reached = [next((k for k, v in enumerate(own) if v >= g["target"]), None) for g in result["goals"]]
    reached = [k for k in reached if k is not None]
    return {"final_net_worth_real": m["final_net_worth_real"], "min_cash": m["min_cash"],
            "liquidity_months": m["liquidity_months"], "final_debt": m["final_debt"],
            "earliest_goal_month": min(reached) if reached else None}


def _fmt(key: str, v) -> str:
    if v is None:
        return "not reached" if key == "earliest_goal_month" else "n/a"
    unit = SLOT_B[key][1]
    if unit == "CHF":
        return f"CHF {v:,.0f}"
    if unit == "months":
        return f"{v:.1f} months"
    return f"month {v + 1}"


def _delta_text(key: str, d, before=None) -> str:
    if d is None:
        return ("not reached before this choice" if key == "earliest_goal_month" and before is None
                else "no comparison with before this choice")
    if abs(d) < (0.05 if SLOT_B[key][1] == "months" else 0.5):
        return "same as before this choice"
    unit = SLOT_B[key][1]
    sign = "+" if d > 0 else "-"
    if unit == "CHF":
        return f"{sign}CHF {abs(d):,.0f} vs before this choice"
    if unit == "months":
        return f"{sign}{abs(d):.1f} months vs before this choice"
    return f"{'later' if d > 0 else 'earlier'} by {abs(d)} months vs before this choice"


def slot_b(result: dict, siblings: list[dict], parent: dict | None) -> dict:
    """What it trades: the metric that differs most from its siblings (gap to the sibling
    median over the sibling spread), with the matching change vs the parent."""
    me = slot_b_values(result)
    group = [me] + [slot_b_values(s) for s in siblings]
    best, best_z = None, 0.0
    for key in SLOT_B:
        vals = [g[key] for g in group]
        if me[key] is None or any(v is None for v in vals) or len(vals) < 2:
            continue
        spread = max(vals) - min(vals)
        gap = abs(me[key] - float(np.median(vals)))
        if spread <= TOL or gap < MATERIAL[SLOT_B[key][1]]:
            continue
        z = gap / spread
        if z > best_z + 1e-12:
            best, best_z = key, z
    basis = "siblings" if best else "default"
    key = best or "final_net_worth_real"
    pv = slot_b_values(parent)[key] if parent else None
    delta = (me[key] - pv) if (pv is not None and me[key] is not None) else None
    label, unit, higher = SLOT_B[key]
    return {"metric": key, "label": label, "unit": unit, "higher_is_better": higher, "value": me[key],
            "basis": basis, "normalised_gap": round(best_z, 3) if best else None,
            "vs_parent": None if delta is None else (round(delta, 2) if unit != "month" else int(delta)),
            "text": f"{label}: {_fmt(key, me[key])}", "vs_parent_text": None if parent is None else _delta_text(key, delta, pv)}


def headline(result: dict, siblings: list[dict] | None = None, parent: dict | None = None) -> dict:
    a = result["headline"]["slot_a"] if result.get("headline") else None
    b = slot_b(result, siblings or [], parent)
    return {"slot_a": a, "slot_b": b, "metric_key": b["metric"]}
