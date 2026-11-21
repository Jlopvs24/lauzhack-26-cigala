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
                "chosen in 'More equities' does not leak into its sibling 'Stay the course'.",
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


# ---------------------------------------------------------------- personal branches (chat / Make it mine)
# The same guarantees on what the user adds: a custom branch (a new option under a node) and patches on an
# existing branch, with the shapes the chat produces (add, set, mul, a new loan, several changes at once).
PERSONAL_BRANCH = {"parent_id": "2", "node_id": "2.c1", "label": "Scholarship + cheaper room", "custom": True,
                   "interventions": [
                       {"param": "monthly_net_income", "op": "add", "value": 600, "from_month": 0, "to_month": 24,
                        "label": "Scholarship"},
                       {"param": "monthly_rent", "op": "mul", "value": 0.9, "from_month": 0, "to_month": 120,
                        "label": "Rent -10%"}]}
PERSONAL_PATCHES = {
    "1.2": [{"param": "monthly_investment_contribution", "op": "set", "value": 300, "from_month": 0, "to_month": 120,
             "label": "Invest CHF 300 a month"},
            {"param": "monthly_other_expenses", "op": "add", "value": -200, "from_month": 0, "to_month": 120,
             "label": "Save CHF 200 more a month"}],
    "2": [{"param": "monthly_net_income", "op": "mul", "value": 0.8, "from_month": 24, "to_month": 120,
           "label": "Work at 80%"},
          {"param": "new_liability", "month": 0, "liability": {"type": "student_loan", "label": "Family loan",
                                                               "principal": 5000, "annual_rate": 0.0,
                                                               "monthly_payment": 150, "payment_start_month": 24}}],
}


def _p(node, custom=None, patches=None, **kw):
    return simulate(None, node, None, sensitivity=False, exploration=False, custom_nodes=custom, node_patches=patches, **kw)


def _under(nid, roots):
    return any(nid == r or nid.startswith(r + ".") for r in roots)


def _personal_identities():
    ids = list(_index(load_tree()))
    runs = [("2.c1", _p("2.c1", [PERSONAL_BRANCH]))]
    runs += [(nid, _p(nid, None, PERSONAL_PATCHES)) for nid in ids if _under(nid, PERSONAL_PATCHES)]
    failed, worst = [], 0.0
    for nid, r in runs:
        for c in r["checks"]:
            worst = max(worst, float(c.get("max_abs_error") or 0.0))
            if not c["passed"]:
                failed.append(f"{nid}:{c['name']}")
    return (not failed, f"A custom branch and two patched branches (with every node below them, {len(runs)} runs) "
                        f"keep all accounting identities; largest error CHF {worst:.2f}.",
            {"custom_branch": PERSONAL_BRANCH["node_id"], "patched": sorted(PERSONAL_PATCHES), "runs": len(runs),
             "failed": failed, "max_abs_error_chf": round(worst, 6)})


def _personal_isolated():
    ids = list(_index(load_tree()))
    leaks, changed = [], []
    for nid in ids:
        base = _p(nid)["metrics"]
        if _p(nid, [PERSONAL_BRANCH])["metrics"] != base:
            leaks.append(f"custom->{nid}")
        moved = _p(nid, None, PERSONAL_PATCHES)["metrics"] != base
        if moved and not _under(nid, PERSONAL_PATCHES):
            leaks.append(f"patch->{nid}")
        if moved:
            changed.append(nid)
    expected = [i for i in ids if _under(i, PERSONAL_PATCHES)]
    ok = not leaks and sorted(changed) == sorted(expected)
    return (ok, f"Adding the custom branch changes no other node, and the patches change exactly the patched branches "
                f"and the nodes below them ({len(expected)} of {len(ids)}), nothing else.",
            {"leaks": leaks, "changed": sorted(changed), "expected": sorted(expected), "nodes": len(ids)})


def _personal_monotone():
    levels, factors = [0, 200, 400, 800], [0.9, 1.0, 1.1, 1.2]

    def branch(extra, rent=1.0):
        ivs = [{"param": "monthly_net_income", "op": "add", "value": extra, "from_month": 0, "to_month": 120,
                "label": "Extra income"},
               {"param": "monthly_rent", "op": "mul", "value": rent, "from_month": 0, "to_month": 120, "label": "Rent"}]
        return [{**PERSONAL_BRANCH, "interventions": ivs}]
    inc = [_p("2.c1", branch(v))["deterministic"]["cash"] for v in levels]
    rent = [_p("2.c1", branch(0, f))["deterministic"]["cash"] for f in factors]
    up = all(all(y >= x - 1e-6 for x, y in zip(a, b)) for a, b in zip(inc, inc[1:]))
    down = all(all(y <= x + 1e-6 for x, y in zip(a, b)) for a, b in zip(rent, rent[1:]))
    strict = all(b[-1] > a[-1] for a, b in zip(inc, inc[1:]))
    return (up and down and strict, "On a personal branch, more income never lowers cash and a higher rent never "
                                    "raises it, in any month (four levels each).",
            {"node": "2.c1", "extra_income_levels": levels, "final_cash_by_income": [round(c[-1], 2) for c in inc],
             "rent_factors": factors, "final_cash_by_rent": [round(c[-1], 2) for c in rent],
             "cash_never_lower_with_more_income": up, "cash_never_higher_with_more_rent": down})


def _personal_reproducible():
    strip = lambda r: {k: v for k, v in r.items() if k != "timing_ms"}  # noqa: E731
    a = _p("2.c1", [PERSONAL_BRANCH], PERSONAL_PATCHES, uncertainty=True, n_paths=300, seed=7)
    b = _p("2.c1", [PERSONAL_BRANCH], PERSONAL_PATCHES, uncertainty=True, n_paths=300, seed=7)
    c = _p("1.2.1", None, PERSONAL_PATCHES, uncertainty=True, n_paths=300, seed=7)
    d = _p("1.2.1", None, PERSONAL_PATCHES, uncertainty=True, n_paths=300, seed=7)
    same = strip(a) == strip(b) and strip(c) == strip(d)
    return (same, "The same personal branch and patches with the same seed reproduce the identical result "
                  "(same trace id), on the custom branch and on a node below a patch.",
            {"custom": {"node": "2.c1", "trace_id": a["trace_id"]}, "patched": {"node": "1.2.1", "trace_id": c["trace_id"]},
             "identical_rerun": same})


CHECKS = [
    ("accounting_identities", "Accounting identities hold on every node", _identities),
    ("reproducibility", "Same inputs and seed reproduce the same result", _reproducible),
    ("monotonicity", "Higher tuition never raises cash", _monotone),
    ("isolation", "Branches are isolated from each other", _isolated),
    ("ubs_starter_kit", "Reproduces the UBS starter kit", _starter),
    ("search_verified", "Exploration thresholds are re-verified", _search_verified),
    ("personal_identities", "Your own branches keep the accounting identities", _personal_identities),
    ("personal_isolation", "Your changes never leak into other branches", _personal_isolated),
    ("personal_monotonicity", "On your branches, more income never lowers cash", _personal_monotone),
    ("personal_reproducibility", "Your branches reproduce exactly", _personal_reproducible),
]


def validation() -> dict:
    t0 = time.perf_counter()
    checks = [_check(cid, label, fn) for cid, label, fn in CHECKS]
    passed = sum(c["passed"] for c in checks)
    return {"engine_version": ENGINE_VERSION, "passed": passed, "total": len(checks), "all_passed": passed == len(checks),
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1), "checks": checks,
            "how": "Runs on demand against the live tree and default assumptions, plus a sample custom branch and "
                   "patches like the ones the chat creates; the same checks run in python -m pytest core/tests -q."}
