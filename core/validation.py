"""Live validation (for the 'technical execution & validation' criterion): the engine checks
itself on demand and reports pass/fail with the evidence, so the UI can show it next to the
tree. Same checks as core/tests, run against the live tree and default assumptions.

    core.validation() -> {passed, total, all_passed, engine_version, duration_ms, checks: [...]}
"""
from __future__ import annotations

import time

from .simulate import ENGINE_VERSION
from .starter import simulate_starter
from .tree import _index, load_tree, simulate

# UBS LauzHack starter kit: the three scenarios and the numbers its own code prints
STARTER_PROFILE = {"name": "Alexia", "opening_cash_chf": 8000, "horizon_months": 120}
STARTER = [
    ("Start working", {"phases": [{"start_month": 0, "end_month": 120, "monthly_income_chf": 4200, "monthly_expenses_chf": 3000}],
                       "one_off_costs": []}, 152000.0, 9200.0, None),
    ("Master's degree", {"phases": [{"start_month": 0, "end_month": 24, "monthly_income_chf": 1200, "monthly_expenses_chf": 2100},
                                    {"start_month": 24, "end_month": 120, "monthly_income_chf": 4800, "monthly_expenses_chf": 3100}],
                         "one_off_costs": [{"month": 0, "amount_chf": 2500}, {"month": 12, "amount_chf": 2500}]},
     144600.0, -18600.0, 6),
    ("Move abroad", {"phases": [{"start_month": 0, "end_month": 120, "monthly_income_chf": 3700, "monthly_expenses_chf": 2900}],
                     "one_off_costs": [{"month": 0, "amount_chf": 6500}]}, 97500.0, 2300.0, None),
]


def _fast(node, overrides=None, **kw):
    return simulate(None, node, overrides, sensitivity=False, exploration=False, **kw)


def _check(cid, label, fn):
    t0 = time.perf_counter()
    try:
        passed, detail, evidence = fn()
    except Exception as e:  # noqa: BLE001 - a crash is a failed check, reported as such
        passed, detail, evidence = False, f"Check crashed: {type(e).__name__}: {e}", {}
    return {"id": cid, "label": label, "passed": bool(passed), "detail": detail, "evidence": evidence,
            "ms": round((time.perf_counter() - t0) * 1000, 1)}


def _identities():
    tree = load_tree()
    nodes, failed, worst = 0, [], 0.0
    for nid in _index(tree):
        r = _fast(nid)
        nodes += 1
        for c in r["checks"]:
            worst = max(worst, float(c.get("max_abs_error") or 0.0))
            if not c["passed"]:
                failed.append(f"{nid}:{c['name']}")
    names = [c["name"] for c in r["checks"]]
    return (not failed, f"{nodes} nodes x {len(names)} checks; largest identity error CHF {worst:.2f}.",
            {"nodes": nodes, "checks": names, "failed": failed, "max_abs_error_chf": round(worst, 6)})


def _reproducible():
    a = _fast("2", uncertainty=True, n_paths=300, seed=7)
    b = _fast("2", uncertainty=True, n_paths=300, seed=7)
    c = _fast("2", uncertainty=True, n_paths=300, seed=8)
    strip = lambda r: {k: v for k, v in r.items() if k != "timing_ms"}  # noqa: E731
    same = strip(a) == strip(b)
    differs = a["bands"] != c["bands"]
    det_same = a["deterministic"] == c["deterministic"]
    return (same and differs and det_same,
            "Same inputs and seed give an identical result (same trace id); another seed changes only the "
            "uncertainty bands, never the deterministic path.",
            {"node": "2", "seed": 7, "n_paths": 300, "trace_id": a["trace_id"], "identical_rerun": same,
             "other_seed_changes_bands": differs, "deterministic_unchanged": det_same})


def _monotone():
    tree = load_tree()
    tuition = next(x for x in tree["assumptions"] if x["id"] == "AS-alexia-master-tuition")
    lo, hi = tuition["range"]
    levels = [lo + (hi - lo) * k / 4 for k in range(5)]
    runs = [_fast("2", {"AS-alexia-master-tuition": v}) for v in levels]
    finals = [r["metrics"]["final_cash"] for r in runs]
    mins = [r["metrics"]["min_cash"] for r in runs]
    month_ok = all(all(y <= x + 1e-6 for x, y in zip(a["deterministic"]["cash"], b["deterministic"]["cash"]))
                   for a, b in zip(runs, runs[1:]))
    ok = all(y < x for x, y in zip(finals, finals[1:])) and all(y <= x for x, y in zip(mins, mins[1:])) and month_ok
    return (ok, "Raising the master's tuition never raises cash, in any month (node 2, five levels across its range).",
            {"node": "2", "assumption": "AS-alexia-master-tuition", "levels": [round(v, 2) for v in levels],
             "final_cash": finals, "min_cash": mins, "cash_never_higher_month_by_month": month_ok})


def _isolated():
    base = _fast("1")
    moved = _fast("1", {"AS-alexia-move-cost": 9000})  # an assumption only the 'move abroad' branch uses
    eq = _fast("1.2.3")
    plain = _fast("1.2.1")
    leak = {x["id"]: x["value"] for x in plain["assumptions_used"]}["AS-investment-return"]
    ok = base["metrics"] == moved["metrics"] and leak != {x["id"]: x["value"] for x in eq["assumptions_used"]}["AS-investment-return"]
    return (ok, "Changing the cost of moving abroad leaves 'Start working' untouched, and the riskier portfolio "
                "chosen in 1.2.3 does not leak into its sibling 1.2.1.",
            {"unrelated_override": {"node": "1", "assumption": "AS-alexia-move-cost", "value": 9000,
                                    "metrics_identical": base["metrics"] == moved["metrics"]},
             "decision_scope": {"node": "1.2.3", "sibling": "1.2.1", "sibling_return": leak}})


def _starter():
    rows, ok = [], True
    for name, sc, closing, minimum, first in STARTER:
        m = simulate_starter(STARTER_PROFILE, {"name": name, **sc})["metrics"]
        match = (m["final_cash"], m["min_cash"], m["first_negative_month"]) == (closing, minimum, first)
        ok &= match
        rows.append({"scenario": name, "closing_cash": m["final_cash"], "expected_closing_cash": closing,
                     "min_cash": m["min_cash"], "expected_min_cash": minimum,
                     "first_negative_month": m["first_negative_month"], "expected_first_negative_month": first, "match": match})
    return (ok, "Under the UBS starter kit's own assumptions (cash only) the engine reproduces its three scenarios exactly.",
            {"scenarios": rows})


def _search_verified():
    ex = simulate(None, "2")["exploration"]
    row = next(r for r in ex["break_even"] if r["compared_to"] == "1")
    th = row["salary_threshold"]
    if th["status"] != "threshold_found":
        return True, f"No break-even inside the salary range (status {th['status']}); nothing to re-check.", {"status": th["status"]}
    sid, v = th["assumption_id"], th["value"]
    gap_at = _fast("2", {sid: v})["metrics"]["final_net_worth"] - _fast("1", {sid: v})["metrics"]["final_net_worth"]
    gap_below = _fast("2", {sid: v - 1})["metrics"]["final_net_worth"] - _fast("1", {sid: v - 1})["metrics"]["final_net_worth"]
    return (gap_at >= 0 > gap_below,
            f"The break-even salary found by the search (CHF {v:,.2f}) is re-simulated: at it the master's ends level "
            "or ahead of working, CHF 1 lower it ends behind.",
            {"node": "2", "compared_to": "1", "assumption": sid, "threshold": v,
             "gap_at_threshold_chf": round(gap_at, 2), "gap_one_chf_below": round(gap_below, 2)})


CHECKS = [
    ("accounting_identities", "Accounting identities hold on every node", _identities),
    ("reproducibility", "Same inputs and seed reproduce the same result", _reproducible),
    ("monotonicity", "Higher tuition never raises cash", _monotone),
    ("isolation", "Branches are isolated from each other", _isolated),
    ("ubs_starter_kit", "Reproduces the UBS starter kit", _starter),
    ("search_verified", "Exploration thresholds are re-verified", _search_verified),
]


def validation() -> dict:
    t0 = time.perf_counter()
    checks = [_check(cid, label, fn) for cid, label, fn in CHECKS]
    passed = sum(c["passed"] for c in checks)
    return {"engine_version": ENGINE_VERSION, "passed": passed, "total": len(checks), "all_passed": passed == len(checks),
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1), "checks": checks,
            "how": "Runs on demand against the live tree and default assumptions; the same checks run in "
                   "python -m pytest core/tests -q."}
