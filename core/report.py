"""Engine data for the path report (#27, docs/report-spec.md section 3).

``report_data`` gathers every number the report shows for one chosen path, so the API
only aggregates and words it (any sentence must be checked against these fields):
each decision on the path with its exploration and tornado, the alternatives at every
level (pruned siblings are simulated here, on demand), the status-quo baseline, and
the leaf under every named weather scenario side by side.
"""
from __future__ import annotations

from .assumptions import build_assumptions
from .models import Profile
from .plan import WEATHER_TYPES, headline
from .simulate import DEFAULT_PATHS, DEFAULT_SEED, ENGINE_VERSION, simulate_node
from .tree import (_index, _personal_tree, for_profile, assumptions_introduced, comparators, describe_intervention, flatten_interventions,
                   lineage, load_profile, load_tree, normalise_path, normalise_weather,
                   personal_flags)

LIMITATIONS = [
    "Synthetic profile and illustrative figures (UBS starter kit); assumptions with verified=false are modelling choices.",
    "Deterministic 'if these inputs hold, then...' paths under stated assumptions: not a forecast and not financial advice.",
    "Income tax: official ESTV 2026 rates for the city and household (abroad: one assumed rate) at today's prices; no wealth or church tax. Pillar 3a payments are deducted and locked (in net worth, not liquid); pillar 2 savings are shown apart, not in net worth.",
    "One currency (CHF) with a constant exchange rate; non-financial assets (car, property) are not modelled.",
    "Shocks in the optional uncertainty lens are independent; its shares of paths are not real-world probabilities.",
    "Every number comes from the engine; the language model only words them and cannot compute new figures.",
]


def summary(res: dict) -> dict:
    m = res["metrics"]
    return {"final_net_worth_real": m["final_net_worth_real"], "final_net_worth": m["final_net_worth"],
            "min_cash": m["min_cash"], "first_negative_month": m["first_negative_month"],
            "final_debt": m["final_debt"], "liquidity_months": m["liquidity_months"],
            "goals_met": sum(g["met_deterministic"] for g in res["goals"]), "goals_total": len(res["goals"]),
            "plan_check": res["plan_check"]["level"], "plan_check_label": res["plan_check"]["label"]}


def _provenance(profile: dict) -> list[dict]:
    prov = profile.get("provenance", {}) or {}
    rows = []
    for key in ("cash", "monthly_net_income", "monthly_rent", "monthly_other_expenses",
                "monthly_investment_contribution", "assets", "liabilities", "goals"):
        if key not in profile:
            continue
        p = prov.get(key, {})
        src = str(p.get("source", ""))
        label = ("synthetic" if src.startswith("ubs_kit") else "assumption" if src.startswith("assumption")
                 else "observed" if src.startswith(("document", "extract")) else "user-entered")
        rows.append({"field": key, "value": profile[key], "label": label, "source": src or None,
                     "confidence": p.get("confidence")})
    return rows


def report_data(profile: dict | None = None, path: list[str] | str | None = None,
                assumptions: list[dict] | dict | None = None, weather: list | None = None, *,
                tree: dict | None = None, uncertainty: bool = False,
                n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED,
                custom_nodes: list[dict] | None = None, node_patches: dict | None = None) -> dict:
    tree = tree or load_tree()
    profile = profile or load_profile()
    tree = for_profile(tree, profile, assumptions)
    prof = Profile.from_dict(profile)
    aset = build_assumptions(tree.get("assumptions", []), assumptions)
    tree = _personal_tree(tree, custom_nodes, node_patches, prof, aset)
    values = aset.values()
    idx = _index(tree)
    path = normalise_path(tree, path)
    root_id = str(tree["root"]["node_id"])
    leaf = path[-1] if path else root_id
    wx = normalise_weather(weather)

    def sim(nid, *, full=False, wthr=None, lens=False):
        node = idx[nid][0]
        return simulate_node(prof, flatten_interventions(tree, nid), assumptions=aset,
                             weather=wx if wthr is None else wthr, node_id=nid, n_paths=n_paths, seed=seed,
                             sensitivity=full, exploration=full, include_flows=full, uncertainty=lens,
                             own_interventions=node.get("interventions", []) or [],
                             comparators=comparators(tree, nid) if full else [])

    baseline = sim(root_id)
    steps, parent_res = [], baseline
    for nid in path:
        node, parent = idx[nid]
        res = sim(nid, full=True)
        peers = []
        for sib in idx[parent][0].get("children", []) or []:
            sid = str(sib["node_id"])
            if sid != nid:
                peers.append((sib, sim(sid)))
        res["headline"] = headline(res, [p for _, p in peers], parent_res)
        ivs = node.get("interventions", []) or []
        steps.append({
            "node_id": nid, "parent_id": parent, "label": node.get("label", nid),
            "description": node.get("description", ""), "catalog": node.get("catalog", []),
            "depth": len(lineage(tree, nid)) - 1, "interventions": ivs,
            "changes": [describe_intervention(iv, values) for iv in ivs],
            "assumptions_introduced": assumptions_introduced(ivs, aset),
            "delta_vs_parent": {k: (round(res["metrics"][k] - parent_res["metrics"][k], 2)
                                    if res["metrics"][k] is not None and parent_res["metrics"][k] is not None else None)
                                for k in ("final_net_worth_real", "final_net_worth", "min_cash", "final_debt",
                                          "liquidity_months")},
            "headline": res["headline"],
            **personal_flags(tree, nid),
            "result": res,
            "alternatives": [{"node_id": str(s["node_id"]), "label": s.get("label", s["node_id"]),
                              "status": "sibling", "custom": bool(s.get("custom")), "summary": summary(r),
                              "headline": headline(r, [res] + [q for t, q in peers if t is not s], parent_res)}
                             for s, r in peers],
        })
        parent_res = res

    leaf_res = steps[-1]["result"] if steps else sim(root_id, full=True)
    stress = [{"weather": "none", "summary": summary(leaf_res)}]
    for kind in WEATHER_TYPES:
        given = [w for w in wx if w.get("type") != kind] + [{"type": kind}]
        try:
            stress.append({"weather": kind, "summary": summary(sim(leaf, wthr=given))})
        except ValueError as e:  # default start month outside a short horizon
            stress.append({"weather": kind, "status": "not_applicable", "detail": str(e)})

    lens = None
    if uncertainty:
        r = sim(leaf, lens=True)
        lens = {"n_paths": r["n_paths"], "seed": r["seed"], "bands": r["bands"],
                "final_net_worth_p10": r["metrics"]["final_net_worth_p10"],
                "final_net_worth_p50": r["metrics"]["final_net_worth_p50"],
                "final_net_worth_p90": r["metrics"]["final_net_worth_p90"],
                "shortfall_probability": r["metrics"]["shortfall_probability"],
                "note": "Shares of simulated paths under these assumptions, not real-world probabilities."}

    return {
        "engine_version": ENGINE_VERSION,
        "question": {"tree_id": tree.get("tree_id"), "profile_id": prof.profile_id, "as_of": prof.as_of.isoformat(),
                     "horizon_months": prof.horizon_months, "currency": "CHF",
                     "jurisdiction": "Switzerland (Lausanne, Vaud): illustrative tax table",
                     "values": "nominal CHF; '_real' fields are in today's prices",
                     "path": [root_id] + path,
                     "question": " -> ".join(idx[n][0].get("label", n) for n in [root_id] + path)},
        "starting_state": _provenance(profile),
        "personal": {"custom_nodes": [n for n in idx if idx[n][0].get("custom")],
                     "patched_nodes": [n for n in idx if idx[n][0].get("patched")]},
        "baseline": {"node_id": root_id, "label": tree["root"].get("label", root_id),
                     "summary": summary(baseline), "headline": baseline["headline"]},
        "steps": steps,
        "leaf": {"node_id": leaf, "constraints": leaf_res["constraints"], "plan_check": leaf_res["plan_check"],
                 "weather_resilience": leaf_res["weather_resilience"],
                 "monthly_surplus": [round(a - b, 2) for a, b in zip(
                     leaf_res["deterministic"]["cash"][1:], leaf_res["deterministic"]["cash"][:-1])]},
        "stress": stress,
        "uncertainty": lens,
        "validation": {"checks": leaf_res["checks"], "seed": seed, "engine_version": ENGINE_VERSION,
                       "trace_id": leaf_res["trace_id"],
                       "reproduce": {"route": "/tree/expand", "profile": profile, "path": path,
                                     "assumptions": assumptions, "weather": wx,
                                     **({"custom_nodes": custom_nodes} if custom_nodes else {}),
                                     **({"node_patches": node_patches} if node_patches else {})},
                       "tests": {"command": "python -m pytest core/tests -q",
                                 "evidence": ["test_identities_hold_in_rich_scenario (accounting identities)",
                                              "test_scenario_isolation_unrelated_assumption_has_no_effect (isolation)",
                                              "test_node_assumption_value_applies_to_its_branch_only_and_user_override_wins (isolation)",
                                              "test_higher_tuition_never_helps (monotonicity)",
                                              "test_break_even_salary_is_where_the_two_paths_meet (exploration)"]}},
        "limitations": LIMITATIONS,
        "condition": "If these inputs hold, then these consequences follow under the stated assumptions.",
    }
