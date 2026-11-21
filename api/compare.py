"""Side-by-side comparison of 2-4 options from any branches (POST /tree/compare). No LLM.

For each path: the option's deterministic result (headline, plan check, key metrics, net-worth and cash series)
and `impact_alone` = what this option's OWN decision changes, as deltas vs its parent node (the same path without
the last decision) and vs today / status quo (the root continued unchanged). `ranking_by` orders the options per
metric with its direction; there is no "best": the user weighs the trade-offs.

Every number comes from core.expand (lean, cached in core's LRU after warm-up), one call per path.
"""
from __future__ import annotations

import time
from typing import Any

from api import engine

# metric -> (label, higher_is_better)
METRICS: dict[str, tuple[str, bool]] = {
    "final_net_worth_real": ("Net worth after the horizon (today's prices)", True),
    "final_net_worth": ("Net worth after the horizon (nominal)", True),
    "min_cash": ("Lowest cash", True),
    "funding_gap": ("Funding gap (deepest negative cash)", False),
    "funding_gap_months": ("Months with negative cash", False),
    "goals_met": ("Goals met", True),
    "liquidity_months": ("Liquidity at the tightest month (months of costs)", True),
    "final_debt": ("Debt at the end", False),
}
DELTA_KEYS = ("final_net_worth_real", "final_net_worth", "min_cash", "funding_gap", "funding_gap_months",
              "goals_met", "liquidity_months", "final_debt")


def key_metrics(res: dict) -> dict:
    m = res.get("metrics") or {}
    cash = (res.get("deterministic") or {}).get("cash") or []
    goals = res.get("goals") or []
    min_cash = m.get("min_cash")
    return {
        "final_net_worth_real": m.get("final_net_worth_real"),
        "final_net_worth": m.get("final_net_worth"),
        "min_cash": min_cash,
        "min_cash_month": m.get("min_cash_month"),
        "first_negative_month": m.get("first_negative_month"),
        "funding_gap": round(max(0.0, -min_cash), 2) if min_cash is not None else None,
        "funding_gap_months": sum(1 for c in cash[1:] if c < -0.01),
        "goals_met": sum(1 for g in goals if g.get("met_deterministic")),
        "goals_total": len(goals),
        "liquidity_months": m.get("liquidity_months"),
        "final_debt": m.get("final_debt"),
    }


def _deltas(a: dict, b: dict) -> dict:
    return {k: (round(a[k] - b[k], 2) if isinstance(a.get(k), (int, float)) and isinstance(b.get(k), (int, float))
                else None) for k in DELTA_KEYS}


def _plan_check(res: dict) -> dict | None:
    pc = res.get("plan_check")
    if not pc:
        return None
    return {k: pc.get(k) for k in ("level", "feasible", "label")} | {
        "failed": [f.get("name") if isinstance(f, dict) else f for f in pc.get("failed") or []]}


def _label(n: dict | None) -> str | None:
    return (n or {}).get("label")


def compare(profile: dict | None, paths: list[list[str]], assumptions: list[dict] | None = None,
            weather: list | None = None, baseline: str = "parent") -> dict:
    t0 = time.perf_counter()
    clean = [[str(p) for p in path if p and str(p) != "0"] for path in paths]
    if not 2 <= len(clean) <= 4:
        raise ValueError("paths must hold 2 to 4 node paths")
    if any(not p for p in clean):
        raise ValueError("each path needs at least one decision (today alone is the status quo baseline)")
    if len({tuple(p) for p in clean}) != len(clean):
        raise ValueError("paths must be different")
    options, today = [], None
    for i, path in enumerate(clean):
        tree = engine.expand(profile, path, assumptions, weather, exploration=False, sensitivity=False)
        by_id = {n["node_id"]: n for n in tree["nodes"] if n.get("result")}
        node, root = by_id.get(path[-1]), by_id.get(tree["path"][0] if tree.get("path") else "0")
        if node is None:
            raise ValueError(f"node {path[-1]!r} not found")
        parent_id = node.get("parent_id") or (path[-2] if len(path) > 1 else (root or {}).get("node_id"))
        parent = by_id.get(parent_id) or root
        res = node["result"]
        km = key_metrics(res)
        pm = key_metrics(parent["result"]) if parent else None
        tm = key_metrics(root["result"]) if root else None
        if today is None and root:
            today = {"node_id": root["node_id"], "label": _label(root), **tm,
                     "plan_check": _plan_check(root["result"])}
        own = {"decision": _label(node), "changes": node.get("changes") or [],
               "vs_parent": {"node_id": parent_id, "label": _label(parent), "delta": _deltas(km, pm) if pm else None},
               "vs_today": {"node_id": (root or {}).get("node_id"), "label": _label(root),
                            "delta": _deltas(km, tm) if tm else None}}
        h = res.get("headline") or {}
        options.append({
            "key": f"{i}:{node['node_id']}", "index": i, "node_id": node["node_id"], "label": _label(node),
            "path": ["0"] + path, "path_labels": [_label(by_id.get(p)) or p for p in path],
            "custom": bool(node.get("custom")), "patched": bool(node.get("patched")),
            "headline": {"does_it_hold": (h.get("slot_a") or {}).get("text"),
                         "what_it_trades": (h.get("slot_b") or {}).get("text")} if h else None,
            "plan_check": _plan_check(res),
            "metrics": km,
            "series": {"net_worth": (res.get("deterministic") or {}).get("net_worth") or [],
                       "net_worth_real": (res.get("deterministic") or {}).get("net_worth_real") or [],
                       "cash": (res.get("deterministic") or {}).get("cash") or []},
            "impact_alone": own,
            "delta": own["vs_today"]["delta"] if baseline == "today" else own["vs_parent"]["delta"],
            "trace_id": res.get("trace_id"),
        })
    ranking = {}
    for k, (label, higher) in METRICS.items():
        vals = [(o["key"], o["metrics"].get(k)) for o in options if isinstance(o["metrics"].get(k), (int, float))]
        vals.sort(key=lambda kv: kv[1], reverse=higher)
        ranking[k] = {"label": label, "direction": "higher first" if higher else "lower first",
                      "order": [{"key": kk, "value": v} for kk, v in vals],
                      "tied": len({v for _, v in vals}) < len(vals)}
    return {
        "options": options, "today": today, "baseline": baseline, "ranking_by": ranking,
        "months": "0-based, as in the engine (month 6 = 'month 7')",
        "reading": "deterministic if-then paths under the same assumptions; orders are per metric, not a verdict",
        "horizon_months": (options[0] and len(options[0]["series"]["cash"]) - 1) or None,
        "compute_ms": int((time.perf_counter() - t0) * 1000),
    }
