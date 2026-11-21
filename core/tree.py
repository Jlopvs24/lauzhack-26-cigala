"""Lazy decision tree with pruning.

Given the path the user has chosen, only these nodes exist (and are simulated):
- the root and every node on the chosen path      -> status "root" / "chosen"
- the siblings of the focus node (greyed out)     -> status "sibling"
- the children of the focus node (next options)   -> status "child"
Everything else is "pruned" and never simulated. Going back one level is just
``path[:-1]``. The full tree is never expanded.
"""
from __future__ import annotations

import json
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .assumptions import AssumptionSet, build_assumptions
from .models import Profile
from . import plan as pl
from .simulate import DEFAULT_PATHS, DEFAULT_SEED, simulate_node, trace_id
from .weather import weather_catalog

DATA = Path(__file__).resolve().parent / "data"
_CACHE: "OrderedDict[str, dict]" = OrderedDict()
_CACHE_MAX = 2048
_LOCK = threading.Lock()  # the API may call the engine from several threads


def load_tree(name: str = "alexia") -> dict:
    return json.loads((DATA / "trees" / f"{name}.json").read_text(encoding="utf-8"))


def load_profile(name: str = "alexia") -> dict:
    return json.loads((DATA / "profiles" / f"{name}.json").read_text(encoding="utf-8"))


def _index(tree: dict) -> dict[str, tuple[dict, str | None]]:
    """node_id -> (node, parent_id)."""
    out: dict[str, tuple[dict, str | None]] = {}

    def walk(node: dict, parent: str | None):
        nid = str(node["node_id"])
        if nid in out:
            raise ValueError(f"duplicate node_id {nid!r}")
        out[nid] = (node, parent)
        for ch in node.get("children", []) or []:
            walk(ch, nid)

    walk(tree["root"], None)
    return out


def lineage(tree: dict, node_id: str) -> list[dict]:
    idx = _index(tree)
    if node_id not in idx:
        raise ValueError(f"unknown node_id {node_id!r}")
    chain = []
    cur: str | None = node_id
    while cur is not None:
        node, parent = idx[cur]
        chain.append(node)
        cur = parent
    return list(reversed(chain))


def flatten_interventions(tree: dict, node_id: str) -> list[dict]:
    """Interventions root -> node, in order (child refines parent)."""
    out: list[dict] = []
    for n in lineage(tree, node_id):
        out.extend(n.get("interventions", []) or [])
    return out


def normalise_path(tree: dict, path: list[str] | str | None) -> list[str]:
    """Accept a list of chosen node ids (root excluded) or a single focus id."""
    root_id = str(tree["root"]["node_id"])
    if path is None or path == [] or path == root_id:
        return []
    if isinstance(path, str):
        return [str(n["node_id"]) for n in lineage(tree, path)][1:]
    idx = _index(tree)
    path = [str(p) for p in path if str(p) != root_id]
    parent = root_id
    for nid in path:
        if nid not in idx or idx[nid][1] != parent:
            raise ValueError(f"invalid path: {nid!r} is not a child of {parent!r}")
        parent = nid
    return path


def visible_nodes(tree: dict, path: list[str] | str | None) -> list[tuple[dict, str, str | None]]:
    """[(node, status, parent_id)] for the nodes that exist at this point of the exploration."""
    idx = _index(tree)
    path = normalise_path(tree, path)
    root = tree["root"]
    root_id = str(root["node_id"])
    focus = path[-1] if path else root_id
    out = [(root, "root" if path else "focus", None)]
    for nid in path:
        node, parent = idx[nid]
        out.append((node, "focus" if nid == focus else "chosen", parent))
    if path:
        parent = idx[focus][1]
        for sib in idx[parent][0].get("children", []) or []:
            if str(sib["node_id"]) != focus:
                out.append((sib, "sibling", parent))
    for ch in idx[focus][0].get("children", []) or []:
        out.append((ch, "child", focus))
    return out


def pruned_nodes(tree: dict, path: list[str] | str | None) -> list[dict]:
    """Ghost nodes: siblings of every ANCESTOR of the current node on the chosen path
    (the branches the user turned away from earlier). They stay drawn in grey with
    their label only: never simulated, no ``result`` (cost ~0). The current node's own
    siblings are not here; they are ``status: "sibling"`` in ``nodes``."""
    idx = _index(tree)
    path = normalise_path(tree, path)
    out = []
    for nid in path[:-1]:  # ancestors of the current node (the root has no siblings)
        parent = idx[nid][1]
        for sib in idx[parent][0].get("children", []) or []:
            sid = str(sib["node_id"])
            if sid == nid:
                continue
            out.append({
                "node_id": sid,
                "parent_id": parent,
                "label": sib.get("label", sid),
                "status": "pruned",
                "depth": len(lineage(tree, sid)) - 1,
                "has_children": bool(sib.get("children")),
            })
    return out


def describe_intervention(iv: dict, values: dict[str, float]) -> str:
    def val(v: Any) -> float:
        if isinstance(v, dict) and "assumption" in v:
            return values[v["assumption"]] * float(v.get("scale", 1))
        return float(v)

    names = {"monthly_net_income": "net income", "monthly_rent": "rent",
             "monthly_other_expenses": "other living costs",
             "monthly_investment_contribution": "monthly investing"}
    p = iv["param"]
    if p in names:
        win = f"from month {iv.get('from_month', 0) + 1}"
        if iv.get("to_month") is not None:
            win += f" to month {iv['to_month']}"
        v = val(iv.get("value", 0))
        op = iv.get("op", "set")
        if op == "set":
            what = f"{names[p]} = CHF {v:,.0f}/month"
        elif op == "add":
            what = f"{names[p]} {'+' if v >= 0 else '-'} CHF {abs(v):,.0f}/month"
        else:
            what = f"{names[p]} x {v:g}"
        return f"{iv.get('label') or names[p]}: {what} {win}"
    if p in ("one_off_cost", "one_off_income"):
        sign = "cost" if p == "one_off_cost" else "income"
        return f"{iv.get('label') or sign}: one-off {sign} CHF {val(iv.get('value', 0)):,.0f} in month {iv.get('month', 0) + 1}"
    if p == "assumption":
        return f"{iv.get('label') or iv.get('id')}: assumption {iv.get('id')} = {val(iv.get('value', 0)):g} on this branch"
    if p == "cancel_one_off":
        return f"Cancels the one-off '{iv.get('label')}' planned earlier on this path"
    if p == "loan_change":
        what = []
        if iv.get("monthly_payment") is not None:
            what.append(f"payment CHF {val(iv['monthly_payment']):,.0f}/month")
        if iv.get("annual_rate") is not None:
            what.append(f"rate {100 * val(iv['annual_rate']):.1f}%")
        return f"{iv.get('label') or 'Loan change'}: {iv.get('loan')} {' and '.join(what)} from month {iv.get('month', 0) + 1}"
    if p == "new_liability":
        l = iv.get("liability", {})
        return (f"{iv.get('label') or 'Loan'}: borrow CHF {val(l.get('principal', 0)):,.0f} at "
                f"{100 * val(l.get('annual_rate', 0)):.1f}%, CHF {val(l.get('monthly_payment', 0)):,.0f}/month, "
                f"in month {iv.get('month', 0) + 1}")
    return str(iv)


def assumption_refs(ivs: list[dict]) -> list[str]:
    """Ids of the assumptions a node's own interventions use (values, loan terms, node-level sets)."""
    refs = set()
    for iv in ivs:
        if iv.get("param") == "assumption":
            refs.add(iv["id"])
        for v in [iv.get("value"), iv.get("monthly_payment"), iv.get("annual_rate"),
                  *(iv.get("liability") or {}).values()]:
            if isinstance(v, dict) and "assumption" in v:
                refs.add(v["assumption"])
    return sorted(refs)


INTRODUCED_KEYS = ("id", "label", "value", "unit", "range", "kind", "source", "verified", "retrieved", "user_edited")


def assumptions_introduced(ivs: list[dict], aset: AssumptionSet) -> list[dict]:
    """The assumptions a decision introduces, with kind, source and whether the source is verified."""
    out = []
    for ref in assumption_refs(ivs):
        a = aset.get(ref)
        out.append({k: a[k] for k in INTRODUCED_KEYS if k in a})
    return out


DELTA_KEYS = ("final_net_worth", "final_net_worth_p50", "min_cash", "shortfall_probability", "final_cash")


def expand(profile: dict | None = None, path: list[str] | str | None = None,
           assumptions: list[dict] | dict | None = None, weather: list | None = None, *,
           tree: dict | None = None, n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED,
           sensitivity: bool = True, include_flows: bool = False,
           uncertainty: bool = False, exploration: bool = True) -> dict:
    """Visible part of the tree for the chosen ``path``, each node with its SimulationResult.

    path: chosen node ids from the root, e.g. [], ["2"], ["2", "2.2"] (a leading "0" is ignored).
    assumptions: overrides, ``[{"id": ..., "value": ...}]`` or ``{id_or_param: value}``.
    weather: ``["recession", ...]`` or ``[{"type": "recession", "start_month": 6}]``; applied to
    every visible node so comparisons stay like-for-like.
    Sensitivity (tornado), monthly flows and ``exploration`` (deterministic break-even
    against the current node's siblings, goal-seek, reverse stress, timing) are computed
    for the current node only. ``uncertainty=True`` adds the optional Monte Carlo lens to
    every visible node; off by default.
    ``pruned_nodes`` lists the branches turned away from earlier (siblings of every
    ancestor), label only, never simulated.
    """
    tree = tree or load_tree()
    profile = profile or load_profile()
    prof = Profile.from_dict(profile)
    aset = build_assumptions(tree.get("assumptions", []), assumptions)
    values = aset.values()
    path = normalise_path(tree, path)
    vis = visible_nodes(tree, path)
    root_id = str(tree["root"]["node_id"])
    current = path[-1] if path else root_id
    wx = normalise_weather(weather)

    results: dict[str, dict] = {}
    for node, status, _ in vis:
        nid = str(node["node_id"])
        is_cur = nid == current
        results[nid] = _cached_simulate(prof, tree, nid, aset, wx, n_paths, seed,
                                        sensitivity=sensitivity and is_cur, include_flows=include_flows or is_cur,
                                        uncertainty=uncertainty, exploration=exploration and is_cur)

    group: dict[str | None, list[tuple[str, str | None]]] = {}
    for node, _, parent in vis:
        group.setdefault(parent, []).append((str(node["node_id"]), parent))
    nodes = []
    for node, status, parent in vis:
        nid = str(node["node_id"])
        res = results[nid]
        delta = None
        if parent is not None and parent in results:
            pm, m = results[parent]["metrics"], res["metrics"]
            delta = {k: (round(m[k] - pm[k], 3 if k == "shortfall_probability" else 2)
                         if m[k] is not None and pm[k] is not None else None) for k in DELTA_KEYS}
            delta["health_score"] = round(res["health"]["score"] - results[parent]["health"]["score"], 1)
        ivs = node.get("interventions", []) or []
        nodes.append({
            "node_id": nid,
            "parent_id": parent,
            "label": node.get("label", nid),
            "description": node.get("description", ""),
            "status": "chosen" if status in ("root", "focus", "chosen") else status,
            "is_current": nid == current,
            "depth": len(lineage(tree, nid)) - 1,
            "has_children": bool(node.get("children")),
            "interventions": ivs,
            "changes": [describe_intervention(iv, values) for iv in ivs],
            "assumptions_ref": assumption_refs(ivs),
            "assumptions_introduced": assumptions_introduced(ivs, aset),
            "delta_vs_parent": delta,
            # copy: cached results are shared, the headline depends on which siblings are visible
            "result": {**res, "headline": pl.headline(res, [results[o] for o, p in group.get(parent, [])
                                                            if o != nid and o in results],
                                                      results.get(parent))},
        })
    return {
        "tree_id": tree.get("tree_id"),
        "profile_id": prof.profile_id,
        "current": current,
        "path": [root_id] + path,
        "back_path": path[:-1] if path else None,
        "nodes": nodes,
        "pruned_nodes": pruned_nodes(tree, path),
        "weather": wx,
        "weather_options": {w["type"]: w["description"] for w in weather_catalog()},
        "assumptions": aset.to_list(),
    }


def normalise_weather(weather: list | None) -> list[dict]:
    return [{"type": w} if isinstance(w, str) else dict(w) for w in weather or []]


def comparators(tree: dict, node_id: str) -> list[dict]:
    """The node's siblings, each with its flattened interventions (break-even peers)."""
    idx = _index(tree)
    parent = idx[node_id][1]
    if parent is None:
        return []
    return [{"node_id": str(s["node_id"]), "label": s.get("label", str(s["node_id"])),
             "interventions": flatten_interventions(tree, str(s["node_id"]))}
            for s in idx[parent][0].get("children", []) or [] if str(s["node_id"]) != node_id]


def _cached_simulate(prof: Profile, tree: dict, node_id: str, aset: AssumptionSet,
                     weather, n_paths, seed, *, sensitivity: bool, include_flows: bool,
                     uncertainty: bool = False, exploration: bool = False) -> dict:
    ivs = flatten_interventions(tree, node_id)
    peers = comparators(tree, node_id) if exploration else []
    key = trace_id(prof.raw, ivs, aset.to_list(), weather, n_paths, seed, sensitivity, include_flows, node_id,
                   uncertainty, exploration, peers)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    res = simulate_node(prof, ivs, assumptions=aset, weather=weather, node_id=node_id, n_paths=n_paths,
                        seed=seed, sensitivity=sensitivity, include_flows=include_flows,
                        uncertainty=uncertainty, exploration=exploration,
                        own_interventions=_index(tree)[node_id][0].get("interventions", []) or [],
                        comparators=peers)
    with _LOCK:
        _CACHE[key] = res
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return res


def simulate(profile: dict | None = None, node: dict | str | None = None,
             assumptions: list[dict] | dict | None = None, weather: list | None = None, *,
             tree: dict | None = None, n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED,
             sensitivity: bool = True, uncertainty: bool = False, exploration: bool = True) -> dict:
    """One SimulationResult (deterministic; ``uncertainty=True`` adds the Monte Carlo lens,
    ``exploration=True`` adds the what-would-have-to-be-true analyses). ``node`` is a node id of the tree, ``{"node_id": ...}`` (looked up
    in the tree, interventions inherited from its ancestors) or ``{"node_id": ..., "parent_id": ...,
    "interventions": [...]}`` for a node not in the tree (applied on top of its parent's path)."""
    tree = tree or load_tree()
    profile = profile or load_profile()
    aset = build_assumptions(tree.get("assumptions", []), assumptions)
    node = {"node_id": node} if isinstance(node, str) else (node or {"node_id": str(tree["root"]["node_id"])})
    nid = str(node.get("node_id", "custom"))
    idx = _index(tree)
    if nid in idx and node.get("interventions") is None:
        ivs = flatten_interventions(tree, nid)
        own = idx[nid][0].get("interventions", []) or []
        peers = comparators(tree, nid) if exploration else []
    else:
        parent = node.get("parent_id")
        known = parent is not None and str(parent) in idx
        base = flatten_interventions(tree, str(parent)) if known else []
        own = list(node.get("interventions") or [])
        ivs = base + own
        # a custom option is compared with staying on its parent's path
        peers = ([{"node_id": str(parent), "label": idx[str(parent)][0].get("label", str(parent)),
                   "interventions": base}] if known and exploration else [])
    return simulate_node(profile, ivs, assumptions=aset, weather=normalise_weather(weather),
                         node_id=nid, n_paths=n_paths, seed=seed, sensitivity=sensitivity,
                         uncertainty=uncertainty, exploration=exploration, own_interventions=own,
                         comparators=peers)


def node_info(node_id: str, tree: dict | None = None) -> dict:
    """Static description of a node (no simulation)."""
    tree = tree or load_tree()
    idx = _index(tree)
    if node_id not in idx:
        raise ValueError(f"unknown node_id {node_id!r}")
    node, parent = idx[node_id]
    return {"node_id": node_id, "parent_id": parent, "label": node.get("label", node_id),
            "description": node.get("description", ""), "interventions": node.get("interventions", []) or [],
            "children": [str(c["node_id"]) for c in node.get("children", []) or []]}


def assumptions_list(overrides: list[dict] | dict | None = None, tree: dict | None = None) -> list[dict]:
    tree = tree or load_tree()
    return build_assumptions(tree.get("assumptions", []), overrides).to_list()


def explore(profile: dict | None = None, path: list[str] | str | None = None,
            assumptions: list[dict] | dict | None = None, weather: list | None = None, *,
            tree: dict | None = None, n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED) -> dict:
    """The heavy, current-node-only part of ``expand``, for lazy loading: the deterministic
    exploration analyses and the tornado of the node at the end of ``path``. Pair it with
    ``expand(..., exploration=False, sensitivity=False)``, which then stays fast."""
    tree = tree or load_tree()
    profile = profile or load_profile()
    prof = Profile.from_dict(profile)
    aset = build_assumptions(tree.get("assumptions", []), assumptions)
    path = normalise_path(tree, path)
    current = path[-1] if path else str(tree["root"]["node_id"])
    res = _cached_simulate(prof, tree, current, aset, normalise_weather(weather), n_paths, seed,
                           sensitivity=True, include_flows=True, exploration=True)
    return {"node_id": current, "path": [str(tree["root"]["node_id"])] + path, "trace_id": res["trace_id"],
            "exploration": res["exploration"], "sensitivity": res["sensitivity"],
            "plan_check": res["plan_check"]}


def warm(profile: dict | None = None, *, tree: dict | None = None, explore_nodes: bool = False) -> int:
    """Precompute every node of the tree for ``profile`` (default: the demo profile) so the
    first clicks hit the cache. Meant for a background thread at API start-up. Returns the
    number of paths warmed."""
    tree = tree or load_tree()
    idx = _index(tree)
    n = 0
    for nid in idx:
        p = normalise_path(tree, nid)
        expand(profile, p, tree=tree, exploration=False, sensitivity=False)
        if explore_nodes:
            explore(profile, p, tree=tree)
        n += 1
    return n
