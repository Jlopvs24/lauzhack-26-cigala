"""Lazy decision tree with pruning.

Given the path the user has chosen, only these nodes exist (and are simulated):
- the root and every node on the chosen path      -> status "root" / "chosen"
- the siblings of the focus node (greyed out)     -> status "sibling"
- the children of the focus node (next options)   -> status "child"
Everything else is "pruned" and never simulated. Going back one level is just
``path[:-1]``. The full tree is never expanded.
"""
from __future__ import annotations

import copy
import json
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .assumptions import AssumptionSet, build_assumptions
from .models import Profile, parse_interventions
from .schedule import build_schedule
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
                "custom": bool(sib.get("custom")),
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


# --- personal conditions: custom nodes and node patches (plan.md "the tree re-grows") ---

def personalize(tree: dict, custom_nodes: list[dict] | None = None,
                node_patches: dict[str, list[dict]] | None = None) -> dict:
    """The tree with the user's own conditions applied, on a deep copy (the input is untouched).

    custom_nodes: ``[{"parent_id", "node_id", "label", "description"?, "interventions": [...]}]``,
    added as children of ``parent_id`` (a tree node or another custom node, in any order). They
    inherit their ancestors' interventions like normal nodes and are marked ``custom: true``.
    node_patches: ``{node_id: [interventions...]}`` appended to that node's own interventions,
    so the node and its whole subtree recompute; marked ``patched: true`` + ``patch_interventions``.
    Without either argument the tree is returned as is (no copy). Structure is checked here,
    intervention values by ``check_personal`` (it needs the profile and assumptions)."""
    if not custom_nodes and not node_patches:
        return tree
    if custom_nodes is not None and not isinstance(custom_nodes, list):
        raise ValueError("custom_nodes must be a list of {parent_id, node_id, label, interventions}")
    if node_patches is not None and not isinstance(node_patches, dict):
        raise ValueError("node_patches must be an object {node_id: [interventions...]}")
    out = copy.deepcopy(tree)
    idx = _index(out)
    pending, seen = [], set()
    for i, c in enumerate(custom_nodes or []):
        lab = f"custom_nodes[{i}]"
        if not isinstance(c, dict):
            raise ValueError(f"{lab} must be an object")
        nid, parent = c.get("node_id"), c.get("parent_id")
        if not isinstance(nid, str) or not nid.strip():
            raise ValueError(f"{lab}.node_id must be a non-empty string, e.g. '2.c1'")
        if nid in idx or nid in seen:
            raise ValueError(f"{lab}.node_id {nid!r} already exists in the tree")
        if parent is None or not str(parent).strip():
            raise ValueError(f"{lab}.parent_id is required")
        label = c.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"{lab}.label must be a non-empty string")
        if c.get("description") is not None and not isinstance(c["description"], str):
            raise ValueError(f"{lab}.description must be a string")
        _check_shape(c.get("interventions"), f"{lab}.interventions", allow_empty=True)
        seen.add(nid)
        pending.append((lab, str(parent), {"node_id": nid, "label": label,
                                           "description": c.get("description") or "",
                                           "interventions": copy.deepcopy(c["interventions"]),
                                           "custom": True}))
    while pending:  # a parent may be a custom node listed later
        rest = []
        for lab, parent, node in pending:
            if parent in idx:
                idx[parent][0].setdefault("children", []).append(node)
                idx[node["node_id"]] = (node, parent)
            else:
                rest.append((lab, parent, node))
        if len(rest) == len(pending):
            lab, parent, _ = rest[0]
            raise ValueError(f"{lab}.parent_id {parent!r} is not a node of the tree or a custom node")
        pending = rest
    for nid, ivs in (node_patches or {}).items():
        lab = f"node_patches[{nid!r}]"
        if str(nid) not in idx:
            raise ValueError(f"{lab}: unknown node_id {nid!r}")
        _check_shape(ivs, lab, allow_empty=False)
        node = idx[str(nid)][0]
        node["interventions"] = list(node.get("interventions") or []) + copy.deepcopy(ivs)
        node["patched"] = True
        node["patch_interventions"] = copy.deepcopy(ivs)
    return out


def _check_shape(ivs, lab: str, *, allow_empty: bool) -> None:
    if not isinstance(ivs, list) or (not ivs and not allow_empty):
        raise ValueError(f"{lab} must be a {'' if allow_empty else 'non-empty '}list of interventions")
    for j, iv in enumerate(ivs):
        if not isinstance(iv, dict) or not isinstance(iv.get("param"), str):
            raise ValueError(f"{lab}[{j}] must be an intervention object with a 'param'")


def check_personal(tree: dict, prof: Profile, aset: AssumptionSet) -> None:
    """Validate custom and patched nodes with the normal intervention schema, in context: the
    assumptions their ancestors set resolve, and the whole path must build (e.g. a
    ``monthly_gross_income`` needs the profile's ``age`` and no ``take_home`` basis;
    ``cancel_one_off`` needs a matching one-off). Raises ``ValueError`` naming the node."""
    for nid, (node, _) in _index(tree).items():
        if node.get("custom"):
            own, where = node.get("interventions") or [], f"custom node {nid!r} interventions"
        elif node.get("patched"):
            own, where = node["patch_interventions"], f"node_patches[{nid!r}]"
        else:
            continue
        try:
            flat = flatten_interventions(tree, nid)
            A = aset.with_node_values(flat).values()
            parse_interventions(own, A, prof.horizon_months, where=where)
            build_schedule(prof, parse_interventions(flat, A, prof.horizon_months), A)
        except (ValueError, KeyError, TypeError) as e:
            msg = str(e)
            raise ValueError(msg if msg.startswith(where) else f"{where}: {msg}") from None


def _personal_tree(tree, custom_nodes, node_patches, prof, aset) -> dict:
    out = personalize(tree, custom_nodes, node_patches)
    if out is not tree:
        check_personal(out, prof, aset)
    return out


def personal_flags(tree: dict, node_id: str, chain: list[dict] | None = None) -> dict:
    """Output markers: ``custom``, ``patched`` (+ ``patch_interventions``), and
    ``inherits_patch`` when an ancestor was patched (its numbers moved too)."""
    chain = chain or lineage(tree, node_id)
    node = chain[-1]
    out = {"custom": bool(node.get("custom")), "patched": bool(node.get("patched")),
           "inherits_patch": any(a.get("patched") for a in chain[:-1])}
    if node.get("patched"):
        out["patch_interventions"] = node["patch_interventions"]
    return out


DELTA_KEYS = ("final_net_worth", "final_net_worth_p50", "min_cash", "shortfall_probability", "final_cash")


def expand(profile: dict | None = None, path: list[str] | str | None = None,
           assumptions: list[dict] | dict | None = None, weather: list | None = None, *,
           tree: dict | None = None, n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED,
           sensitivity: bool = True, include_flows: bool = False,
           uncertainty: bool = False, exploration: bool = True,
           custom_nodes: list[dict] | None = None, node_patches: dict | None = None) -> dict:
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
    ``custom_nodes`` / ``node_patches``: the user's own conditions (see ``personalize``).
    """
    tree = tree or load_tree()
    profile = profile or load_profile()
    prof = Profile.from_dict(profile)
    aset = build_assumptions(tree.get("assumptions", []), assumptions)
    tree = _personal_tree(tree, custom_nodes, node_patches, prof, aset)
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
        chain = lineage(tree, nid)
        nodes.append({
            "node_id": nid,
            "parent_id": parent,
            "label": node.get("label", nid),
            "description": node.get("description", ""),
            "status": "chosen" if status in ("root", "focus", "chosen") else status,
            "is_current": nid == current,
            "depth": len(chain) - 1,
            "has_children": bool(node.get("children")),
            "interventions": ivs,
            "changes": [describe_intervention(iv, values) for iv in ivs],
            "assumptions_ref": assumption_refs(ivs),
            "assumptions_introduced": assumptions_introduced(ivs, aset),
            "delta_vs_parent": delta,
            **personal_flags(tree, nid, chain),
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
    own = _index(tree)[node_id][0].get("interventions", []) or []
    # the key covers the FULL flattened interventions (patches and custom nodes included), the
    # node's own part (timing) and the peers (break-even), so personal trees never collide
    key = trace_id(prof.raw, ivs, aset.to_list(), weather, n_paths, seed, sensitivity, include_flows, node_id,
                   uncertainty, exploration, peers, own)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    res = simulate_node(prof, ivs, assumptions=aset, weather=weather, node_id=node_id, n_paths=n_paths,
                        seed=seed, sensitivity=sensitivity, include_flows=include_flows,
                        uncertainty=uncertainty, exploration=exploration,
                        own_interventions=own, comparators=peers)
    with _LOCK:
        _CACHE[key] = res
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return res


def simulate(profile: dict | None = None, node: dict | str | None = None,
             assumptions: list[dict] | dict | None = None, weather: list | None = None, *,
             tree: dict | None = None, n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED,
             sensitivity: bool = True, uncertainty: bool = False, exploration: bool = True,
             custom_nodes: list[dict] | None = None, node_patches: dict | None = None) -> dict:
    """One SimulationResult (deterministic; ``uncertainty=True`` adds the Monte Carlo lens,
    ``exploration=True`` adds the what-would-have-to-be-true analyses). ``node`` is a node id of the tree, ``{"node_id": ...}`` (looked up
    in the tree, interventions inherited from its ancestors) or ``{"node_id": ..., "parent_id": ...,
    "interventions": [...]}`` for a node not in the tree (applied on top of its parent's path).
    ``custom_nodes`` / ``node_patches``: the user's own conditions (see ``personalize``)."""
    tree = tree or load_tree()
    profile = profile or load_profile()
    aset = build_assumptions(tree.get("assumptions", []), assumptions)
    if custom_nodes or node_patches:
        tree = _personal_tree(tree, custom_nodes, node_patches, Profile.from_dict(profile), aset)
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


def node_info(node_id: str, tree: dict | None = None, *, custom_nodes: list[dict] | None = None, node_patches: dict | None = None) -> dict:
    """Static description of a node (no simulation)."""
    tree = personalize(tree or load_tree(), custom_nodes, node_patches)
    idx = _index(tree)
    if node_id not in idx:
        raise ValueError(f"unknown node_id {node_id!r}")
    node, parent = idx[node_id]
    return {"node_id": node_id, "parent_id": parent, "label": node.get("label", node_id),
            "description": node.get("description", ""), "interventions": node.get("interventions", []) or [],
            "children": [str(c["node_id"]) for c in node.get("children", []) or []],
            **personal_flags(tree, node_id)}


def assumptions_list(overrides: list[dict] | dict | None = None, tree: dict | None = None) -> list[dict]:
    tree = tree or load_tree()
    return build_assumptions(tree.get("assumptions", []), overrides).to_list()


def explore(profile: dict | None = None, path: list[str] | str | None = None,
            assumptions: list[dict] | dict | None = None, weather: list | None = None, *,
            tree: dict | None = None, n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED,
            custom_nodes: list[dict] | None = None, node_patches: dict | None = None) -> dict:
    """The heavy, current-node-only part of ``expand``, for lazy loading: the deterministic
    exploration analyses and the tornado of the node at the end of ``path``. Pair it with
    ``expand(..., exploration=False, sensitivity=False)``, which then stays fast."""
    tree = tree or load_tree()
    profile = profile or load_profile()
    prof = Profile.from_dict(profile)
    aset = build_assumptions(tree.get("assumptions", []), assumptions)
    tree = _personal_tree(tree, custom_nodes, node_patches, prof, aset)
    path = normalise_path(tree, path)
    current = path[-1] if path else str(tree["root"]["node_id"])
    res = _cached_simulate(prof, tree, current, aset, normalise_weather(weather), n_paths, seed,
                           sensitivity=True, include_flows=True, exploration=True)
    return {"node_id": current, "path": [str(tree["root"]["node_id"])] + path, "trace_id": res["trace_id"],
            "exploration": res["exploration"], "sensitivity": res["sensitivity"],
            "plan_check": res["plan_check"]}


def warm(profile: dict | None = None, *, tree: dict | None = None, explore_nodes: bool = False,
         custom_nodes: list[dict] | None = None, node_patches: dict | None = None) -> int:
    """Precompute every node of the tree for ``profile`` (default: the demo profile) so the
    first clicks hit the cache. Meant for a background thread at API start-up. Returns the
    number of paths warmed. With ``custom_nodes`` / ``node_patches`` it warms that personal tree
    (same cache keys as the matching ``expand`` / ``explore`` calls)."""
    tree = tree or load_tree()
    kw = {"custom_nodes": custom_nodes, "node_patches": node_patches}
    full = personalize(tree, custom_nodes, node_patches)
    n = 0
    for nid in _index(full):
        p = normalise_path(full, nid)
        expand(profile, p, tree=tree, exploration=False, sensitivity=False, **kw)
        if explore_nodes:
            explore(profile, p, tree=tree, **kw)
        n += 1
    return n
