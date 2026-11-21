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
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .assumptions import AssumptionSet, build_assumptions
from .models import Profile
from .simulate import DEFAULT_PATHS, DEFAULT_SEED, simulate_node, trace_id
from .weather import weather_catalog

DATA = Path(__file__).resolve().parent / "data"
_CACHE: "OrderedDict[str, dict]" = OrderedDict()
_CACHE_MAX = 512


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
    if p == "new_liability":
        l = iv.get("liability", {})
        return (f"{iv.get('label') or 'Loan'}: borrow CHF {float(l.get('principal', 0)):,.0f} at "
                f"{100 * float(l.get('annual_rate', 0)):.1f}%, CHF {float(l.get('monthly_payment', 0)):,.0f}/month, "
                f"in month {iv.get('month', 0) + 1}")
    return str(iv)


DELTA_KEYS = ("final_net_worth", "final_net_worth_p50", "min_cash", "shortfall_probability", "final_cash")


def expand(profile: dict | None = None, path: list[str] | str | None = None,
           assumptions: list[dict] | dict | None = None, weather: list | None = None, *,
           tree: dict | None = None, n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED,
           sensitivity: bool = True, include_flows: bool = False) -> dict:
    """Visible part of the tree for the chosen ``path``, each node with its SimulationResult.

    path: chosen node ids from the root, e.g. [], ["2"], ["2", "2.2"] (a leading "0" is ignored).
    assumptions: overrides, ``[{"id": ..., "value": ...}]`` or ``{id_or_param: value}``.
    weather: ``["recession", ...]`` or ``[{"type": "recession", "start_month": 6}]``; applied to
    every visible node so comparisons stay like-for-like.
    Sensitivity (tornado) and monthly flows are computed for the current node only.
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
                                        sensitivity=sensitivity and is_cur, include_flows=include_flows or is_cur)

    nodes = []
    for node, status, parent in vis:
        nid = str(node["node_id"])
        res = results[nid]
        delta = None
        if parent is not None and parent in results:
            pm, m = results[parent]["metrics"], res["metrics"]
            delta = {k: round(m[k] - pm[k], 3 if k == "shortfall_probability" else 2) for k in DELTA_KEYS}
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
            "assumptions_ref": sorted({iv["value"]["assumption"] for iv in ivs
                                       if isinstance(iv.get("value"), dict) and "assumption" in iv["value"]}),
            "delta_vs_parent": delta,
            "result": res,
        })
    return {
        "tree_id": tree.get("tree_id"),
        "profile_id": prof.profile_id,
        "current": current,
        "path": [root_id] + path,
        "back_path": path[:-1] if path else None,
        "nodes": nodes,
        "weather": wx,
        "weather_options": {w["type"]: w["description"] for w in weather_catalog()},
        "assumptions": aset.to_list(),
    }


def normalise_weather(weather: list | None) -> list[dict]:
    return [{"type": w} if isinstance(w, str) else dict(w) for w in weather or []]


def _cached_simulate(prof: Profile, tree: dict, node_id: str, aset: AssumptionSet,
                     weather, n_paths, seed, *, sensitivity: bool, include_flows: bool) -> dict:
    ivs = flatten_interventions(tree, node_id)
    key = trace_id(prof.raw, ivs, aset.to_list(), weather, n_paths, seed, sensitivity, include_flows, node_id)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    res = simulate_node(prof, ivs, assumptions=aset, weather=weather, node_id=node_id, n_paths=n_paths,
                        seed=seed, sensitivity=sensitivity, include_flows=include_flows)
    _CACHE[key] = res
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return res


def simulate(profile: dict | None = None, node: dict | str | None = None,
             assumptions: list[dict] | dict | None = None, weather: list | None = None, *,
             tree: dict | None = None, n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED,
             sensitivity: bool = True) -> dict:
    """One SimulationResult. ``node`` is a node id of the tree, ``{"node_id": ...}`` (looked up
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
    else:
        parent = node.get("parent_id")
        ivs = flatten_interventions(tree, str(parent)) if parent is not None and str(parent) in idx else []
        ivs = ivs + list(node.get("interventions") or [])
    return simulate_node(profile, ivs, assumptions=aset, weather=normalise_weather(weather),
                         node_id=nid, n_paths=n_paths, seed=seed, sensitivity=sensitivity)


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
