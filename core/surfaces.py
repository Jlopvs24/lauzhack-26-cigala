"""Combined decisions, two-lever surfaces, constraint-targeted search, timing scan (#48 item 6).

All deterministic ("if these inputs hold, then..."), batched through ``run_batch``, and judged
with the same constraints and plan level as a node's ``plan_check``:
- ``combine(node_a, node_b)``: path A plus B's own decisions below their common ancestor
  (later interventions win; overlaps are listed as ``conflicts``).
- ``surface(path, x, y)``: a small grid of two levers (assumptions or monthly changes) -> plan
  level, final net worth, min cash per cell, and optionally the difference to a peer node (its
  zero contour is the break-even line). For a heatmap.
- ``smallest_change(path, target)``: per lever, the smallest change that makes the plan reach
  the target (default: no funding gap).
- ``timing_scan(path)``: the node's own decision started 0..36 months later -> plan level and
  final net worth; the latest start that still holds.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from . import analysis as an
from . import plan as pl
from .assumptions import build_assumptions
from .engine import run_batch
from .explore import shift_interventions, threshold
from .models import SERIES_PARAMS, Profile, parse_interventions
from .schedule import build_schedule
from .weather import build_weather

LEVEL_ORDER = ("holds", "holds_below_target", "infeasible", "needs_financing")
FEASIBLE = ("holds", "holds_below_target")
CONDITION = "If these inputs hold, then these consequences follow under the stated assumptions. Not a forecast."
MAX_CELLS = 121


# ---------------------------------------------------------------- context and batched evaluation
def _context(profile, path, assumptions, weather, tree, custom_nodes, node_patches):
    from . import tree as tr
    tree = tree or tr.load_tree()
    profile = profile or tr.load_profile()
    prof = profile if isinstance(profile, Profile) else Profile.from_dict(profile)
    aset = build_assumptions(tree.get("assumptions", []), assumptions)
    tree = tr._personal_tree(tree, custom_nodes, node_patches, prof, aset)
    path = tr.normalise_path(tree, path)
    current = path[-1] if path else str(tree["root"]["node_id"])
    ivs = tr.flatten_interventions(tree, current)
    own = list(tr.lineage(tree, current)[-1].get("interventions", []))
    return SimpleNamespace(tree=tree, prof=prof, aset=aset, node=current, ivs=ivs, own=own,
                           weather=tr.normalise_weather(weather))


def evaluate(prof: Profile, cases: list[tuple[list[dict], object]], weather: list[dict]) -> list[dict]:
    """Deterministic plan level and key numbers for many (interventions, assumption set) cases."""
    H = prof.horizon_months
    values = [a.with_node_values(ivs).values() for ivs, a in cases]
    scheds = [build_schedule(prof, parse_interventions(ivs, v, H), v) for (ivs, _), v in zip(cases, values)]
    out = run_batch(scheds, values, prof.cash, prof.investments, prof.tax_table(cases[0][1]),
                    build_weather(weather, H), stochastic=False, keep_flows=True)
    rows = []
    for j, ((ivs, a), A) in enumerate(zip(cases, values)):
        det = SimpleNamespace(cash=out.cash[j:j + 1], investments=out.investments[j:j + 1],
                              pillar_3a=out.pillar_3a[j:j + 1], debt=out.debt[j], net_worth=out.net_worth[j:j + 1],
                              flows={k: v[j:j + 1] for k, v in out.flows.items()})
        goals = an.evaluate_goals(prof, det, None)
        cons = pl.constraints(det, A, goals, a.with_node_values(ivs))
        level = pl.plan_level(cons)
        cash = out.cash[j]
        rows.append({"level": level, "feasible": level in FEASIBLE,
                     "failed": [c["name"] for c in cons if not c["passed"] and c["kind"] != "target"],
                     "final_net_worth": an.r2(out.net_worth[j, -1]),
                     "final_net_worth_real": an.r2(out.net_worth[j, -1] / out.cpi[j, -1]),
                     "min_cash": an.r2(cash[1:].min()), "first_negative_month": an.first_negative(cash)})
    return rows


# ---------------------------------------------------------------- levers
LEVER_PARAMS = SERIES_PARAMS


def _lever(spec: dict, aset, H: int, n: int, label: str):
    """A lever -> (description, values, f(value) -> (extra interventions, assumption set))."""
    if not isinstance(spec, dict):
        raise ValueError(f"{label} must be an object")
    if "assumption" in spec:
        a = aset._find(str(spec["assumption"]))
        if a is None:
            raise ValueError(f"{label}: unknown assumption {spec['assumption']!r}")
        vals = spec.get("values")
        if vals is None:
            if not a.get("range"):
                raise ValueError(f"{label}: assumption {a['id']} has no range; give values")
            vals = np.linspace(a["range"][0], a["range"][1], n)
        desc = {"kind": "assumption", "assumption_id": a["id"], "label": a.get("label", a["param"]),
                "unit": a.get("unit", ""), "base_value": a["value"]}
        return desc, [float(v) for v in vals], lambda v: ([], aset.with_overrides({a["id"]: v}))
    param = spec.get("param")
    if param not in LEVER_PARAMS:
        raise ValueError(f"{label}: give an assumption id or a param in {LEVER_PARAMS}")
    op = spec.get("op", "add")
    if op not in ("add", "set"):
        raise ValueError(f"{label}.op must be add or set")
    vals = spec.get("values")
    if vals is None:
        rng = spec.get("range")
        if not (isinstance(rng, (list, tuple)) and len(rng) == 2):
            raise ValueError(f"{label}: give values or range [low, high]")
        vals = np.linspace(float(rng[0]), float(rng[1]), n)
    base = {"param": param, "op": op, "from_month": int(spec.get("from_month", 0)), "label": spec.get("label", "lever")}
    if spec.get("to_month") is not None:
        base["to_month"] = int(spec["to_month"])
    if spec.get("currency"):
        base["currency"] = spec["currency"]
    desc = {"kind": "change", "param": param, "op": op, "from_month": base["from_month"],
            "to_month": base.get("to_month"), "currency": spec.get("currency", "CHF"),
            "label": spec.get("label") or f"{param} {op}", "unit": f"{spec.get('currency', 'CHF')}/month"}
    return desc, [float(v) for v in vals], lambda v: ([{**base, "value": v}], aset)


# ---------------------------------------------------------------- 1. combine
def combine(profile: dict | None = None, node_a: str = "", node_b: str = "", assumptions=None, weather=None, *,
            tree: dict | None = None, custom_nodes=None, node_patches=None) -> dict:
    """Path to ``node_a`` plus ``node_b``'s own decisions below their common ancestor."""
    from . import tree as tr
    from .simulate import simulate_node
    ctx = _context(profile, node_a, assumptions, weather, tree, custom_nodes, node_patches)
    tree = ctx.tree
    la, lb = tr.lineage(tree, str(node_a)), tr.lineage(tree, str(node_b))
    common = 0
    while common < min(len(la), len(lb)) and la[common]["node_id"] == lb[common]["node_id"]:
        common += 1
    if common == len(lb):
        raise ValueError(f"{node_b} is {node_a} or one of its ancestors: nothing to combine")
    if common == len(la):
        raise ValueError(f"{node_a} is an ancestor of {node_b}: open {node_b} instead")
    a_ivs = tr.flatten_interventions(tree, str(node_a))
    b_own = [iv for n in lb[common:] for iv in n.get("interventions", [])]
    conflicts = []
    H = ctx.prof.horizon_months
    for ib in b_own:
        for ia in a_ivs:
            if ia.get("param") != ib.get("param") or ia["param"] not in SERIES_PARAMS + ("tax_residence",):
                continue
            a0, a1 = ia.get("from_month", 0), ia.get("to_month") or H
            b0, b1 = ib.get("from_month", 0), ib.get("to_month") or H
            lo, hi = max(a0, b0), min(a1, b1)
            if lo < hi and (ib.get("op", "set") == "set" or ib["param"] == "tax_residence"):
                conflicts.append({"param": ib["param"], "from_month": lo, "to_month": hi,
                                  "overridden": ia.get("label", ""), "by": ib.get("label", ""),
                                  "rule": "later wins: B's decision replaces A's in these months"})
    nid = f"{node_a}+{node_b}"
    res = simulate_node(ctx.prof, a_ivs + b_own, assumptions=ctx.aset, weather=ctx.weather, node_id=nid,
                        sensitivity=False, exploration=False, include_flows=True)
    ra = evaluate(ctx.prof, [(a_ivs, ctx.aset), (tr.flatten_interventions(tree, str(node_b)), ctx.aset)], ctx.weather)
    summary = {"combined": {"level": res["plan_check"]["level"] if "plan_check" in res else None,
                            "final_net_worth": res["metrics"]["final_net_worth"], "min_cash": res["metrics"]["min_cash"]},
               "a": ra[0], "b": ra[1]}
    return {"node_id": nid, "node_a": str(node_a), "node_b": str(node_b),
            "common_ancestor": la[common - 1]["node_id"], "added_from_b": b_own, "conflicts": conflicts,
            "compare": summary, "result": res, "basis": "deterministic", "condition": CONDITION}


# ---------------------------------------------------------------- 2. two-lever surface
def surface(profile: dict | None = None, path=None, x: dict | None = None, y: dict | None = None, *,
            n: int = 7, compare_to: str | None = None, assumptions=None, weather=None, tree: dict | None = None,
            custom_nodes=None, node_patches=None) -> dict:
    """Grid of two levers at the node at the end of ``path``. ``x`` / ``y``: ``{"assumption": id,
    "values"?: [...]}`` (default: n points over its range) or ``{"param": monthly series, "op":
    "add"|"set", "values" | "range": [lo, hi], "from_month"?, "to_month"?, "currency"?}``.
    ``cells[i][j]`` is y value i, x value j. With ``compare_to`` (a node id), each cell also has
    ``delta_vs_peer`` = this node's final net worth minus the peer's under the same assumption
    values (change levers apply to this node only); its sign change is the break-even line."""
    if not x or not y:
        raise ValueError("give two levers x and y")
    if not (2 <= int(n) <= 11):
        raise ValueError("n must be in 2..11")
    ctx = _context(profile, path, assumptions, weather, tree, custom_nodes, node_patches)
    H = ctx.prof.horizon_months
    dx, xv, fx = _lever(x, ctx.aset, H, int(n), "x")
    dy, yv, fy = _lever(y, ctx.aset, H, int(n), "y")
    if len(xv) * len(yv) > MAX_CELLS:
        raise ValueError(f"at most {MAX_CELLS} cells")
    if dx["kind"] == "assumption" and dy["kind"] == "assumption" and dx["assumption_id"] == dy["assumption_id"]:
        raise ValueError("x and y must be different levers")
    cases, peers = [], []
    peer_ivs = None
    if compare_to is not None:
        from . import tree as tr
        peer_ivs = tr.flatten_interventions(ctx.tree, str(compare_to))
    for vy in yv:
        for vx in xv:
            ex_y, a_y = fy(vy)
            ex_x, _ = fx(vx)
            if dx["kind"] == "assumption":
                a = a_y.with_overrides({**_overrides(a_y), dx["assumption_id"]: vx})
            else:
                a = a_y
            cases.append((ctx.ivs + ex_y + ex_x, a))
            if peer_ivs is not None:
                peers.append((peer_ivs, a))
    rows = evaluate(ctx.prof, cases + peers, ctx.weather)
    mine, theirs = rows[:len(cases)], rows[len(cases):]
    cells = []
    for i in range(len(yv)):
        row = []
        for j in range(len(xv)):
            k = i * len(xv) + j
            c = {**mine[k], "x": xv[j], "y": yv[i]}
            if theirs:
                c["delta_vs_peer"] = an.r2(mine[k]["final_net_worth"] - theirs[k]["final_net_worth"])
            row.append(c)
        cells.append(row)
    flat = [c for r in cells for c in r]
    return {"node_id": ctx.node, "x": {**dx, "values": xv}, "y": {**dy, "values": yv}, "cells": cells,
            "levels": list(LEVEL_ORDER), "holds_share": round(sum(c["feasible"] for c in flat) / len(flat), 3),
            "compare_to": compare_to, "basis": "deterministic", "condition": CONDITION}


def _overrides(aset) -> dict:
    return {a["id"]: a["value"] for a in aset.items if a.get("user_edited")}


# ---------------------------------------------------------------- 3. constraint-targeted search
TARGETS = {"no_funding_gap": "cash never negative", "feasible": "plan holds (no funding gap, hard limits and goals met)",
           "holds": "plan holds with every target met"}


def smallest_change(profile: dict | None = None, path=None, target: str = "no_funding_gap", *,
                    levers: list[dict] | None = None, assumptions=None, weather=None, tree: dict | None = None,
                    custom_nodes=None, node_patches=None) -> dict:
    """Per lever, the smallest change (from month 0 to the horizon unless the lever says
    otherwise) that makes the node reach ``target``. Default levers: more net income per month,
    lower rent, lower other living costs, a one-off amount of cash in month 0."""
    if target not in TARGETS:
        raise ValueError(f"target must be one of {tuple(TARGETS)}")
    ctx = _context(profile, path, assumptions, weather, tree, custom_nodes, node_patches)
    prof, H = ctx.prof, ctx.prof.horizon_months
    A = ctx.aset.with_node_values(ctx.ivs).values()
    sched = build_schedule(prof, parse_interventions(ctx.ivs, A, H), A)
    default = [
        {"name": "more_income", "label": "More net income every month", "param": "monthly_net_income", "sign": 1,
         "high": 20000.0, "unit": "CHF/month (today's prices)"},
        {"name": "lower_rent", "label": "Lower rent every month", "param": "monthly_rent", "sign": -1,
         "high": float(sched.rent.max()), "unit": "CHF/month (today's prices)"},
        {"name": "lower_living_costs", "label": "Lower other living costs every month", "param": "monthly_other_expenses",
         "sign": -1, "high": float(sched.other_expenses.max()), "unit": "CHF/month (today's prices)"},
        {"name": "cash_now", "label": "Extra cash in month 0 (savings, family, a grant)", "param": "one_off_income",
         "sign": 1, "high": 1_000_000.0, "unit": "CHF once"},
    ]
    specs = levers or default

    def ok_margin(row):
        if target == "no_funding_gap":
            return row["min_cash"] + an.TOL
        if target == "feasible":
            return 1.0 if row["feasible"] else -1.0
        return 1.0 if row["level"] == "holds" else -1.0

    base = evaluate(prof, [(ctx.ivs, ctx.aset)], ctx.weather)[0]
    out = []
    for s in specs:
        name, param, sign = s.get("name", s.get("param")), s.get("param"), float(s.get("sign", 1))
        if param not in SERIES_PARAMS + ("one_off_income", "one_off_cost"):
            raise ValueError(f"lever {name}: param must be a monthly series or a one-off")
        lo, hi = float(s.get("low", 0.0)), float(s.get("high", 0.0))
        row = {"lever": name, "label": s.get("label", name), "param": param, "unit": s.get("unit", "CHF/month"),
               "direction": "increase" if sign > 0 else "decrease"}
        if hi <= lo:
            out.append({**row, "status": "lever_has_no_room", "value": None})
            continue

        def ivs_for(v, param=param, sign=sign, s=s):
            if param.startswith("one_off"):
                return ctx.ivs + [{"param": param, "month": int(s.get("month", 0)), "value": float(v), "label": "lever"}]
            iv = {"param": param, "op": "add", "value": sign * float(v), "from_month": int(s.get("from_month", 0)), "label": "lever"}
            if s.get("to_month") is not None:
                iv["to_month"] = int(s["to_month"])
            return ctx.ivs + [iv]

        def margins(values):
            rows = evaluate(prof, [(ivs_for(v), ctx.aset) for v in values], ctx.weather)
            return np.array([ok_margin(r) for r in rows])

        ans = threshold(margins, lo, hi)
        res = {**row, **ans}
        if ans["status"] in ("threshold_found", "already_satisfied") and ans["value"] is not None:
            res["result"] = evaluate(prof, [(ivs_for(ans["value"]), ctx.aset)], ctx.weather)[0]
        out.append(res)
    return {"node_id": ctx.node, "target": target, "target_means": TARGETS[target], "now": base,
            "already_holds": ok_margin(base) >= 0, "changes": out, "basis": "deterministic", "condition": CONDITION}


# ---------------------------------------------------------------- 4. timing scan
def timing_scan(profile: dict | None = None, path=None, *, delays: list[int] | None = None, assumptions=None,
                weather=None, tree: dict | None = None, custom_nodes=None, node_patches=None) -> dict:
    """This node's own decision started later (ancestors keep their dates; the horizon end is fixed)."""
    ctx = _context(profile, path, assumptions, weather, tree, custom_nodes, node_patches)
    H = ctx.prof.horizon_months
    delays = list(range(0, 37, 6)) if delays is None else [int(d) for d in delays]
    if not ctx.own:
        return {"node_id": ctx.node, "status": "no_own_decision", "rows": []}
    parent = ctx.ivs[:len(ctx.ivs) - len(ctx.own)]
    valid = [d for d in delays if 0 <= d < H]
    rows = evaluate(ctx.prof, [(parent + shift_interventions(ctx.own, d, H), ctx.aset) for d in valid], ctx.weather)
    table = [{"delay_months": d, **r} for d, r in zip(valid, rows)]
    holding = [r["delay_months"] for r in table if r["feasible"]]
    contiguous = None
    for r in table:
        if not r["feasible"]:
            break
        contiguous = r["delay_months"]
    return {"node_id": ctx.node, "status": "evaluated", "rows": table,
            "latest_start_that_holds": max(holding) if holding else None,
            "holds_from_now_until": contiguous, "basis": "deterministic", "condition": CONDITION}
