"""Bounded deterministic what-ifs; every answer reuses the accounting engine."""
from __future__ import annotations

import copy
import math

import numpy as np

from .analysis import TOL, first_negative, r2
from .engine import run_batch
from .models import parse_interventions
from .schedule import build_schedule
from .weather import build_weather

PROBES = 16  # points evaluated together per search round (one engine pass)
SEARCH_LIMIT = 1_000_000.0  # Explicit search bound in today's CHF, not a plausible salary or award.


def threshold(evaluate, low, high, *, strict=False):
    """Smallest lever value in [low, high] whose margin is >= 0 (> 0 when ``strict``), to 0.01.

    Statuses: threshold_found, already_satisfied (holds at ``low``), not_reached_within_bounds,
    lever_has_no_effect, non_monotone. Bisection assumes an increasing margin; when a 9-point
    grid contradicts it no threshold is returned rather than a wrong one.
    """
    grid = np.linspace(low, high, 9)
    margins = np.asarray(evaluate(grid), dtype=float)
    if not np.all(np.isfinite(margins)):
        return {"status": "non_monotone", "value": None, "bounds": [low, high]}
    edges = {"margin_at_bounds": [r2(margins[0]), r2(margins[-1])]}
    if np.ptp(margins) <= TOL:
        return {"status": "lever_has_no_effect", "value": None, "bounds": [low, high], **edges}
    passed = margins > 0 if strict else margins >= 0
    if passed.all():
        return {"status": "already_satisfied", "value": low, "bounds": [low, high], **edges}
    if not passed.any():
        return {"status": "not_reached_within_bounds", "value": None, "bounds": [low, high], **edges}
    if np.any(np.diff(margins) < -TOL):
        return {"status": "non_monotone", "value": None, "bounds": [low, high], **edges}
    right = int(np.flatnonzero(passed)[0])
    left, right = float(grid[right - 1]), float(grid[right])
    while right - left > 0.005:  # k-ary search: PROBES points per round, all in one batched engine pass
        pts = np.linspace(left, right, PROBES + 2)[1:-1]
        m = np.asarray(evaluate(pts), dtype=float)
        ok = np.flatnonzero(m > 0 if strict else m >= 0)
        if ok.size:
            i = int(ok[0])
            right, left = float(pts[i]), (float(pts[i - 1]) if i else left)
        else:
            left = float(pts[-1])
    value = math.ceil(right * 100) / 100
    if not ((evaluate([value])[0] > 0) if strict else (evaluate([value])[0] >= 0)):
        return {"status": "not_reached_within_bounds", "value": None, "bounds": [low, high], **edges}
    return {"status": "threshold_found", "value": value, "bounds": [low, high],
            "tolerance": 0.01, **edges}


MAX_LEVERS = 5


def levers(tornado):
    """The assumptions that move this node most, from the deterministic tornado.

    Every lever can be overridden per request with ``assumptions={id: value}``."""
    rows = []
    for r in (tornado or [])[:MAX_LEVERS]:
        rows.append({"assumption_id": r["assumption_id"], "label": r["label"],
                     "unit": r["unit"], "base_value": r["base_value"],
                     "low_value": r["low_value"], "high_value": r["high_value"],
                     "final_net_worth_low": r["final_net_worth_low"],
                     "final_net_worth_high": r["final_net_worth_high"],
                     "swing_final_net_worth": r["delta_final_net_worth"],
                     "cash_shortfall_low": r["cash_shortfall_low"],
                     "cash_shortfall_high": r["cash_shortfall_high"],
                     "how_to_change": {"assumptions": {r["assumption_id"]: r["high_value"]}}})
    return rows


def shift_interventions(interventions, delay, horizon):
    """Delay only the current decision; ancestor interventions keep their dates."""
    shifted = []
    for original in interventions:
        iv = copy.deepcopy(original)
        if iv["param"] == "assumption":  # a change of assumption has no date
            shifted.append(iv)
            continue
        key = "from_month" if iv["param"].startswith("monthly_") or iv["param"] == "tax_residence" else "month"
        iv[key] = iv.get(key, 0) + delay
        if iv[key] >= horizon:
            continue
        if iv.get("to_month") is not None:
            iv["to_month"] = min(horizon, iv["to_month"] + delay)
        if iv["param"] == "new_liability" and "payment_start_month" in iv["liability"]:
            iv["liability"]["payment_start_month"] += delay
        shifted.append(iv)
    return shifted


def explore_node(profile, interventions, own_interventions, aset, weather, comparators, levers):
    """Explore one node, with fixed profile/weather and the same assumption set for peers."""
    H = profile.horizon_months
    wx = build_weather(weather, H)

    def run_cases(cases, keep_flows=False):
        values = [a.with_node_values(ivs).values() for ivs, a in cases]
        schedules = [build_schedule(profile, parse_interventions(ivs, v, H), v) for (ivs, _), v in zip(cases, values)]
        return run_batch(schedules, values, profile.cash,
                         profile.investments, profile.tax_table(aset), wx, stochastic=False, keep_flows=keep_flows)

    def summary(out, row=0):
        cash = out.cash[row]
        return {"final_net_worth": r2(out.net_worth[row, -1]), "final_cash": r2(cash[-1]),
                "min_cash": r2(cash[1:].min()), "first_negative_month": first_negative(cash)}

    base = run_cases([(interventions, aset)])
    goals = []
    for goal in profile.goals:
        k = goal.target_month + 1

        def goal_margin(values):
            cases = [(interventions + [{"param": "monthly_net_income", "op": "add", "value": float(v),
                                       "from_month": 0, "to_month": k}], aset) for v in values]
            out = run_cases(cases)
            wealth = out.cash[:, k] + out.investments[:, k]
            if goal.metric == "net_worth":
                wealth = wealth + out.pillar_3a[:, k] - out.debt[:, k]
            return wealth - goal.target

        answer = threshold(goal_margin, 0.0, SEARCH_LIMIT)
        goals.append({"goal": goal.name, "target": goal.target, "target_month": goal.target_month,
                      "metric": goal.metric, "lever": "additional_monthly_net_income",
                      "from_month": 0, "to_month": k, "unit": "CHF/month in month-0 prices, then indexed like other income (inflation + real wage growth)",
                      **answer})

    def breaking_margin(values):
        cases = [(interventions + [{"param": "one_off_cost", "month": 0, "value": float(v)}], aset)
                 for v in values]
        out = run_cases(cases)
        margins = out.cash[:, 1:].min(axis=1) + TOL
        for goal in profile.goals:
            k = goal.target_month + 1
            wealth = out.cash[:, k] + out.investments[:, k]
            if goal.metric == "net_worth":
                wealth += out.pillar_3a[:, k] - out.debt[:, k]
            margins = np.minimum(margins, wealth - goal.target)
        return -margins

    reverse = {"lever": "one_off_cost", "month": 0, "unit": "CHF at today's prices",
               "breaks": "cash below -0.01 CHF or any dated goal missed",
               **threshold(breaking_margin, 0.0, SEARCH_LIMIT, strict=True)}
    if reverse["value"] is not None:
        witness = run_cases([(interventions + [{"param": "one_off_cost", "month": 0,
                                               "value": reverse["value"]}], aset)])
        reverse["result"] = summary(witness)
        reverse["missed_goals"] = [g.name for g in profile.goals if
            (witness.cash[0, g.target_month + 1] + witness.investments[0, g.target_month + 1] -
             (witness.debt[0, g.target_month + 1] - witness.pillar_3a[0, g.target_month + 1]
              if g.metric == "net_worth" else 0)) < g.target]
        if reverse["status"] == "already_satisfied":
            reverse["status"] = "already_broken"

    # Search the latest assumption-backed salary, while retaining all other decisions.
    income_ref = next((iv["value"]["assumption"] for iv in reversed(interventions)
                       if iv["param"] == "monthly_net_income" and isinstance(iv.get("value"), dict)
                       and "assumption" in iv["value"]), None)
    salary = aset.get(income_ref) if income_ref else None
    comparisons = []
    for peer in comparators:
        peer_ivs = peer["interventions"]
        peer_out = run_cases([(peer_ivs, aset)])
        difference = base.net_worth[0, 1:] - peer_out.net_worth[0, 1:]
        ahead = np.flatnonzero(difference > TOL)
        stays_ahead = np.logical_and.accumulate((difference >= -TOL)[::-1])[::-1]
        sustained = np.flatnonzero((difference > TOL) & stays_ahead)
        row = {"compared_to": peer["node_id"], "label": peer.get("label", peer["node_id"]),
               "delta_final_net_worth": r2(difference[-1]),
               "first_month_ahead": int(ahead[0]) if ahead.size else None,
               "sustained_crossover_month": int(sustained[0]) if sustained.size else None,
               "salary_threshold": None}
        if salary is not None and salary.get("range"):
            def salary_margin(values):
                cases = []
                for value in values:
                    variant = aset.with_overrides({salary["id"]: float(value)})
                    cases.extend([(interventions, variant), (peer_ivs, variant)])
                final = run_cases(cases).net_worth[:, -1].reshape(-1, 2)
                return final[:, 0] - final[:, 1]

            answer = threshold(salary_margin, *salary["range"])
            if answer["status"] == "already_satisfied":
                answer["value"] = None  # ahead at every salary in range: no salary is "needed"
            row["salary_threshold"] = {"assumption_id": salary["id"], "unit": salary.get("unit"), **answer}
        comparisons.append(row)

    timing = []
    ancestor_count = len(interventions) - len(own_interventions)
    parent_ivs = interventions[:ancestor_count]
    for delay in (12, 24):
        if not own_interventions or delay >= H:
            timing.append({"delay_months": delay, "status": "no_interventions" if not own_interventions else "outside_horizon"})
            continue
        shifted = shift_interventions(own_interventions, delay, H)
        out = run_cases([(parent_ivs + shifted, aset)])
        timing.append({"delay_months": delay, "status": "evaluated", "same_end_month": H - 1,
                       "omitted_interventions": len(own_interventions) - len(shifted),
                       "window_shortened": any(
                           iv["param"].startswith("monthly_") and
                           (iv.get("to_month") is None or iv["to_month"] + delay > H)
                           for iv in own_interventions),
                       **summary(out), "delta_final_net_worth": r2(out.net_worth[0, -1] - base.net_worth[0, -1])})

    return {"basis": "deterministic", "condition": "If these inputs hold, then these consequences follow under the stated assumptions.",
            "levers": levers or [], "break_even": comparisons, "goal_seek": goals,
            "reverse_stress": reverse, "timing": timing,
            "pillar_3a": pillar_3a_options(profile, interventions, aset, run_cases)}


def pillar_3a_options(profile, interventions, aset, run_cases) -> dict:
    """#48 item 4: the same monthly amount (this node's pillar 3a maximum / 12, today's prices)
    paid into pillar 3a, invested, or kept in cash, from month 0 to the horizon, instead of any 3a
    payment the node already plans; plus the largest
    monthly 3a payment that still meets every dated goal (3a money is locked, so it does not
    count for liquid goals). Payments happen only when cash allows."""
    H = profile.horizon_months
    A = aset.with_node_values(interventions).values()
    sched = build_schedule(profile, parse_interventions(interventions, A, H), A)
    earned = sched.gross if sched.gross is not None and (sched.gross > 0).any() else sched.income
    paid = np.flatnonzero(earned > 0)
    if not paid.size:
        return {"status": "no_earned_income", "note": "Pillar 3a needs earned income (or unemployment benefits)."}
    m0 = int(paid[0])
    annual = 12.0 * float(earned[m0])
    has_bvg = annual >= A["payroll_bvg_entry"]
    cap = A["pillar3a_max"] if has_bvg else min(A["pillar3a_no_bvg_share"] * annual, A["pillar3a_max_no_bvg"])
    x = round(cap / 12.0, 2)
    none = {"param": "monthly_pillar_3a", "op": "set", "value": 0.0, "from_month": 0}
    cases = [("keep_in_cash", interventions + [none]),
             ("pay_into_3a", interventions + [{**none, "value": x}]),
             ("invest", interventions + [none, {"param": "monthly_investment_contribution", "op": "add",
                                                "value": x, "from_month": 0}])]
    out = run_cases([(ivs, aset) for _, ivs in cases], keep_flows=True)
    options = []
    for j, (name, _) in enumerate(cases):
        f = out.flows
        options.append({"option": name, "final_net_worth": r2(out.net_worth[j, -1]),
                        "final_liquid": r2(out.cash[j, -1] + out.investments[j, -1]),
                        "final_pillar_3a": r2(out.pillar_3a[j, -1]), "min_cash": r2(out.cash[j, 1:].min()),
                        "paid_into_3a": r2(f["pillar_3a_contribution"][j].sum()),
                        "invested": r2(f["contribution"][j].sum()),
                        "income_tax": r2(f["income_tax"][j].sum()),
                        "tax_saved_by_3a": r2(f["pillar_3a_tax_saving"][j].sum())})
    best = max(options, key=lambda o: o["final_net_worth"])["option"]
    seek = {"status": "no_dated_goals", "value": None}
    if profile.goals:
        def breaking(values):
            res = run_cases([(interventions + [{**none, "value": float(v)}], aset) for v in values])
            margins = np.full(len(values), np.inf)
            for goal in profile.goals:
                k = goal.target_month + 1
                wealth = res.cash[:, k] + res.investments[:, k]
                if goal.metric == "net_worth":
                    wealth = wealth + res.pillar_3a[:, k] - res.debt[:, k]
                margins = np.minimum(margins, wealth - goal.target)
            return -margins
        ans = threshold(breaking, 0.0, x, strict=True)
        st = ans["status"]
        if st == "threshold_found":
            seek = {"status": "found", "value": max(r2(ans["value"] - 0.01), 0.0)}
        elif st in ("not_reached_within_bounds", "lever_has_no_effect"):
            seek = {"status": "full_amount_keeps_goals", "value": x}
        elif st == "already_satisfied":
            seek = {"status": "goals_already_missed", "value": None}
        else:
            seek = {"status": st, "value": None}
    return {"status": "evaluated", "monthly_amount": x, "annual_cap": r2(cap), "has_pension_fund": bool(has_bvg),
            "unit": "CHF/month in month-0 prices, then indexed like other spending; capped per calendar year",
            "options": options, "highest_final_net_worth": best,
            "max_monthly_3a_keeping_goals": seek,
            "note": "3a money is locked until retirement (early withdrawal only for a home, self-employment or leaving Switzerland): it counts in net worth, not in cash, investments or liquid goals."}
