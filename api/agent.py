"""Explanatory agent (the character).

Rules enforced in code, not only in the prompt:
- The LLM never computes: every figure comes from engine tools. After answering, each
  number in the text is checked against the tool outputs; if any is not grounded we
  fall back to the template answer (plan B) and say so in `grounding`.
- It never recommends or decides: it explains possibilities and trade-offs.
- It answers in the user's language.
If the LLM is unavailable or fails, the template answer is returned (`mode: "template"`).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from api import engine, llm

log = logging.getLogger("api.agent")
MAX_ROUNDS = 5
CHARACTER = "Lumi"  # the guide orb (PR #5)


# ------------------------------------------------------------------ tools
TOOLS = [
    {"type": "function", "function": {
        "name": "get_node",
        "description": "Deterministic if-then result of one decision node under the current assumptions: final net "
                       "worth, lowest cash and the month it goes negative (if it does), goals reached or not, levers "
                       "(assumptions that move the result most), accounting checks, trace id. Node '0' is today.",
        "parameters": {"type": "object", "properties": {"node_id": {"type": "string"}}, "required": ["node_id"]}}},
    {"type": "function", "function": {
        "name": "compare_nodes",
        "description": "Side-by-side deterministic results of several nodes (e.g. siblings), with differences vs the first.",
        "parameters": {"type": "object", "properties": {
            "node_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["node_ids"]}}},
    {"type": "function", "function": {
        "name": "what_if",
        "description": "Pull a lever: re-run a node with one assumption set to a new value and return what changes. "
                       "Use get_assumptions to see ids.",
        "parameters": {"type": "object", "properties": {
            "node_id": {"type": "string"}, "assumption_id": {"type": "string"}, "value": {"type": "number"}},
            "required": ["node_id", "assumption_id", "value"]}}},
    {"type": "function", "function": {
        "name": "what_would_have_to_be_true",
        "description": "Answer 'what would have to be true' questions with an engine search (not a forecast): the "
                       "threshold value of an assumption at which (target='cash_never_negative') cash never goes below "
                       "zero, (target='match_other_node') this node's final net worth catches up with other_node_id "
                       "(break-even), or (target='reach_goal') a goal is reached by its date. Also returns the engine's "
                       "own exploration analyses for the node when available (break-even, goal-seek, reverse stress "
                       "test, timing). assumption_id is optional: by default the node's own levers are tried.",
        "parameters": {"type": "object", "properties": {
            "node_id": {"type": "string"},
            "target": {"type": "string", "enum": ["cash_never_negative", "match_other_node", "reach_goal"]},
            "assumption_id": {"type": "string"},
            "other_node_id": {"type": "string"},
            "goal_name": {"type": "string"}},
            "required": ["node_id", "target"]}}},
    {"type": "function", "function": {
        "name": "get_exploration",
        "description": "The engine's own exploration analyses for a node (when the engine provides them): levers, "
                       "break-even / crossover vs siblings, goal-seek (extra income needed for a goal), reverse stress "
                       "(the one-off cost that breaks the plan) and timing (the same decision 12 or 24 months later). "
                       "Optional `kind` filters one of them.",
        "parameters": {"type": "object", "properties": {
            "node_id": {"type": "string"},
            "kind": {"type": "string", "description": "levers | break_even | goal_seek | reverse_stress | timing"}},
            "required": ["node_id"]}}},
    {"type": "function", "function": {
        "name": "get_assumptions",
        "description": "All editable assumptions (levers) with value, unit, range and source.",
        "parameters": {"type": "object", "properties": {}}}},
]


def _refs(node: dict) -> list[str]:
    """Assumption ids a node's interventions reference (core: {"assumption": id}, mock: {"ref": id})."""
    if node.get("assumptions_ref"):
        return list(node["assumptions_ref"])
    out = []
    for iv in node.get("interventions") or []:
        v = iv.get("value")
        if isinstance(v, dict):
            out.append(v.get("assumption") or v.get("ref"))
    return sorted({r for r in out if r})


def _sens(item: dict) -> dict:
    keep = ("assumption_id", "label", "unit", "base_value", "low_value", "high_value", "change",
            "final_net_worth_low", "final_net_worth_high", "delta_final_net_worth")
    return {k: item[k] for k in keep if k in item}


def _diff(a, b):
    return None if a is None or b is None else round(a - b, 2)


def _month(m):
    return None if m is None else m + 1  # engine months are 0-based; people say "month 7"


def _trim(obj: Any, max_chars: int = 3000) -> Any:
    """Keep engine exploration output small enough for the prompt (lists cut to 3 items)."""
    if len(json.dumps(obj, default=str)) <= max_chars:
        return obj
    if isinstance(obj, dict):
        return {k: _trim(v, max_chars // max(len(obj), 1)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_trim(v, max_chars // 3) for v in obj[:3]]
    return obj


def _det(res: dict) -> dict:
    """Deterministic headline numbers of a result (the primary if-then path). Never reads bands."""
    m, d = res.get("metrics") or {}, res.get("deterministic") or {}

    def pick(key, series):
        for v in (m.get(key), d.get(key) if not isinstance(d.get(key), list) else None):
            if v is not None:
                return v
        arr = d.get(series) or []
        return arr[-1] if arr else None

    cash = d.get("cash") or []
    return {"final_net_worth": pick("final_net_worth", "net_worth"),
            "final_cash": pick("final_cash", "cash"),
            "min_cash": m.get("min_cash") if m.get("min_cash") is not None else (min(cash[1:]) if len(cash) > 1 else None),
            "min_cash_month": _month(m.get("min_cash_month")),
            "first_negative_month": _month(m.get("first_negative_month"))}


def _summary(res: dict, node: dict, uncertainty: bool = False) -> dict:
    """Engine-agnostic digest of a SimulationResult. Deterministic first; the Monte Carlo
    lens is included only when the user asked for it (uncertainty=True)."""
    m = res["metrics"]
    comps = res["health"].get("components", {})
    out = {
        "node_id": res["node_id"], "label": node.get("label"), "trace_id": res["trace_id"],
        "engine": res.get("engine") or res.get("engine_version"),
        "reading": "deterministic if-then path under the stated assumptions, not a forecast",
        "weather": [w.get("type") if isinstance(w, dict) else w for w in res.get("weather") or []],
        **_det(res),
        "goals": [{"name": g.get("name"), "target": g.get("target"), "by_month": _month(g.get("target_month")),
                   "reached_on_this_path": g.get("met_deterministic"),
                   "first_reached_month": _month(g.get("first_reached_month_deterministic"))}
                  for g in res.get("goals") or []] or None,
        "liquidity_months": m.get("liquidity_months"),
        "health_score": res["health"]["score"],
        "health_components": {k: (v.get("score") if isinstance(v, dict) else v) for k, v in comps.items()},
        "levers": [_sens(x) for x in (res.get("sensitivity") or [])[:3]],
        "checks_passed": all(c["passed"] for c in res.get("checks", [])),
        "assumptions_used": _refs(node),
        "changes": node.get("changes") or None,
        "description": node.get("description") or None,
        "delta_vs_parent": node.get("delta_vs_parent") or None,
        "horizon_months": res.get("horizon_months"),
    }
    for k in ("final_debt", "total_one_off_costs"):
        if k in m:
            out[k] = m[k]
    if res["health"].get("level"):
        out["health_level"] = res["health"]["level"]
    expl = res.get("exploration") or node.get("exploration")
    if expl:
        out["exploration"] = _trim(expl)
    bands = (res.get("bands") or {}).get("net_worth") or {}
    if uncertainty and bands.get("p50") and res.get("n_paths", 1):
        out["uncertainty_lens"] = {
            "reading": "spread across simulated paths under these assumptions; not a probability of the future",
            "final_net_worth_p10": m.get("final_net_worth_p10", bands["p10"][-1]),
            "final_net_worth_p50": m.get("final_net_worth_p50", bands["p50"][-1]),
            "final_net_worth_p90": m.get("final_net_worth_p90", bands["p90"][-1]),
            "share_of_paths_with_negative_cash": m.get("shortfall_probability"),
            "share_of_paths_reaching_goals": m.get("goal_probability") or None,
            "n_paths": res.get("n_paths")}
    if out["changes"] is None:
        out["interventions"] = node.get("interventions", [])
    return {k: v for k, v in out.items() if v is not None or k == "first_negative_month"}


_TARGETS = ("cash_never_negative", "match_other_node", "reach_goal")


class Toolbox:
    def __init__(self, ctx: dict):
        self.profile = ctx["profile"]
        self.overrides = ctx.get("assumptions") or []
        self.weather = ctx.get("weather") or []
        self.uncertainty = bool(ctx.get("uncertainty"))
        self.cache: dict[str, tuple[dict, dict]] = {}
        self.fast_cache: dict[str, dict] = {}
        self.calls: list[dict] = []

    def _key(self, node_id: str, overrides=None) -> str:
        return node_id + json.dumps(overrides if overrides is not None else self.overrides, sort_keys=True)

    def _node(self, node_id: str, overrides=None) -> tuple[dict, dict]:
        key = self._key(node_id, overrides)
        if key not in self.cache:
            node = engine.node_info(node_id)
            res = engine.simulate(self.profile, {"node_id": node_id},
                                  overrides if overrides is not None else self.overrides, self.weather,
                                  uncertainty=self.uncertainty)
            self.cache[key] = (res, node)
        return self.cache[key]

    def _fast(self, node_id: str, overrides: list[dict]) -> dict:
        """Deterministic headline numbers only (for searches)."""
        key = self._key(node_id, overrides)
        if key not in self.fast_cache:
            res = engine.simulate(self.profile, {"node_id": node_id}, overrides, self.weather, fast=True)
            self.fast_cache[key] = {**_det(res), "goals": {g.get("name"): g.get("met_deterministic")
                                                           for g in res.get("goals") or []}}
        return self.fast_cache[key]

    def get_node(self, node_id: str) -> dict:
        res, node = self._node(str(node_id))
        out = _summary(res, node, self.uncertainty)
        vals = {a["id"]: a for a in engine.assumptions(self.overrides)}
        out["assumption_values"] = {i: {"value": vals[i]["value"], "unit": vals[i].get("unit")}
                                    for i in out["assumptions_used"] if i in vals}
        return out

    def compare_nodes(self, node_ids: list[str]) -> dict:
        rows = [self.get_node(n) for n in node_ids]
        base = rows[0]
        diffs = {r["node_id"]: {
            "final_net_worth_minus_first": _diff(r["final_net_worth"], base["final_net_worth"]),
            "min_cash_minus_first": _diff(r["min_cash"], base["min_cash"])} for r in rows[1:]}
        return {"nodes": rows, "differences_vs_first": diffs}

    def what_if(self, node_id: str, assumption_id: str, value: float) -> dict:
        ids = {a["id"] for a in engine.assumptions()}
        if assumption_id not in ids:
            return {"error": f"unknown assumption {assumption_id}", "valid_ids": sorted(ids)}
        before = self.get_node(node_id)
        ov = [o for o in self.overrides if o.get("id") != assumption_id] + [{"id": assumption_id, "value": value}]
        res, node = self._node(str(node_id), ov)
        after = _summary(res, node, self.uncertainty)
        return {"reading": "if this assumption had this value, then (everything else unchanged)",
                "assumption_id": assumption_id, "new_value": value, "before": before, "after": after,
                "delta_final_net_worth": _diff(after["final_net_worth"], before["final_net_worth"]),
                "delta_min_cash": _diff(after["min_cash"], before["min_cash"])}

    # -------------------------------------------------------- what would have to be true
    def what_would_have_to_be_true(self, node_id: str, target: str, assumption_id: str | None = None,
                                   other_node_id: str | None = None, goal_name: str | None = None) -> dict:
        node_id = str(node_id)
        if target not in _TARGETS:
            return {"error": f"target must be one of {_TARGETS}"}
        if target == "match_other_node" and not other_node_id:
            return {"error": "match_other_node needs other_node_id (e.g. a sibling)"}
        res, node = self._node(node_id)
        out: dict[str, Any] = {"node_id": node_id, "label": node.get("label"), "target": target,
                               "reading": "what would have to be true under the other assumptions; not a forecast"}
        expl = res.get("exploration") or node.get("exploration")
        if expl:
            out["engine_exploration"] = _trim(expl)
        if target == "reach_goal":
            goals = [g.get("name") for g in res.get("goals") or []]
            if not goals:
                out["search"] = {"error": "this engine reports no goals for the node"}
                return out
            goal_name = goal_name if goal_name in goals else goals[0]
            out["goal_name"] = goal_name
        candidates = [assumption_id] if assumption_id else \
            list(dict.fromkeys(_refs(node) + [s["assumption_id"] for s in (res.get("sensitivity") or [])]))
        for aid in [c for c in candidates if c][:3]:
            found = self._search(node_id, target, aid, other_node_id, goal_name)
            if found.get("threshold_value") is not None or assumption_id:
                out["search"] = found
                return out
            out.setdefault("tried", []).append(found)
        out.setdefault("search", {"error": "no lever of this node crosses the target within its range"})
        return out

    def _search(self, node_id, target, aid, other_id, goal_name, iters: int = 16) -> dict:
        info = {a["id"]: a for a in engine.assumptions(self.overrides)}
        if aid not in info:
            return {"assumption_id": aid, "error": "unknown assumption", "valid_ids": sorted(info)}
        a = info[aid]
        cur = float(a["value"])
        rng = a.get("range") or [cur * 0.5, cur * 1.5]
        lo = min(float(rng[0]), cur * 0.25) if cur > 0 else float(rng[0])
        hi = max(float(rng[1]), cur * 3 if cur > 0 else float(rng[1]) * 3 or 1.0)
        runs = 0

        def ok(v: float) -> bool:
            nonlocal runs
            ov = [o for o in self.overrides if o.get("id") != aid] + [{"id": aid, "value": v}]
            r = self._fast(node_id, ov)
            runs += 1
            if target == "cash_never_negative":
                return r["min_cash"] >= 0
            if target == "reach_goal":
                return bool(r["goals"].get(goal_name))
            runs += 1
            return r["final_net_worth"] >= self._fast(str(other_id), ov)["final_net_worth"]

        now, at_lo, at_hi = ok(cur), ok(lo), ok(hi)
        base = {"assumption_id": aid, "label": a.get("label"), "unit": a.get("unit"), "current_value": cur,
                "holds_now": now, "searched_range": [round(lo, 4), round(hi, 4)],
                "method": "deterministic bisection over engine.simulate (api), every point computed by the engine"}
        if at_lo == at_hi:
            base.update(threshold_value=None, holds_across_range=at_lo)
            base["runs"] = runs
            return base
        a_, b_ = (lo, hi)
        for _ in range(iters):
            mid = (a_ + b_) / 2
            if ok(mid) == at_lo:
                a_ = mid
            else:
                b_ = mid
        thr = b_ if at_hi else a_  # the side where the target holds
        step = 10.0 if abs(cur) >= 100 else (0.001 if abs(cur) < 1 else 1.0)
        thr = (round(thr / step) * step) if not at_hi else (-(-thr // step) * step)
        thr = round(thr, 4)
        ov = [o for o in self.overrides if o.get("id") != aid] + [{"id": aid, "value": thr}]
        at = self._fast(node_id, ov)
        base.update(threshold_value=thr, direction="at least" if at_hi else "at most",
                    change_from_current=round(thr - cur, 4),
                    result_at_threshold={k: at[k] for k in ("final_net_worth", "min_cash", "first_negative_month")},
                    runs=runs)
        if target == "match_other_node":
            base["other_node_id"] = other_id
            base["other_final_net_worth_at_threshold"] = self._fast(str(other_id), ov)["final_net_worth"]
        return base

    def preload(self, node_id: str) -> list[dict]:
        """Current node + siblings + children via one engine expand (free) so most questions need one LLM call.
        Recorded as a tool call so grounding and traces include it."""
        try:
            tree = engine.expand(self.profile, engine.path_to(node_id), self.overrides, self.weather,
                                 uncertainty=self.uncertainty)
        except Exception as e:  # noqa: BLE001
            log.warning("preload failed: %s", e)
            return []
        for n in tree["nodes"]:
            self.cache[self._key(n["node_id"])] = (n["result"], n)
        order = {"chosen": 1, "sibling": 2, "child": 3}
        vis = sorted((n for n in tree["nodes"] if n["node_id"] == node_id or n["status"] in ("sibling", "child")),
                     key=lambda n: (n["node_id"] != node_id, order.get(n["status"], 9)))
        ids = [n["node_id"] for n in vis]
        rows = [{**self.get_node(i), "status": n["status"]} for i, n in zip(ids, vis)]
        self.calls.append({"tool": "preload", "args": {"node_ids": ids}, "result": {"nodes": rows}})
        return rows

    def get_exploration(self, node_id: str, kind: str | None = None) -> dict:
        res, node = self._node(str(node_id))
        expl = res.get("exploration") or node.get("exploration")
        if not expl:
            return {"node_id": node_id, "available": False,
                    "hint": "use what_would_have_to_be_true for an engine-computed threshold search"}
        if kind:
            match = {k: v for k, v in expl.items() if kind.replace("_", "") in k.replace("_", "")}                 if isinstance(expl, dict) else {}
            expl = match or {"error": f"no {kind!r} in exploration", "available_kinds": list(expl)}
        return {"node_id": str(node_id), "label": node.get("label"), "available": True,
                "reading": "what would have to be true / what changes, under these assumptions; not a forecast",
                "exploration": _trim(expl, 6000)}

    def get_assumptions(self) -> dict:
        return {"assumptions": engine.assumptions(self.overrides)}

    def run(self, name: str, args: dict) -> dict:
        try:
            out = getattr(self, name)(**args) if name in {t["function"]["name"] for t in TOOLS} \
                else {"error": f"unknown tool {name}"}
        except Exception as e:  # noqa: BLE001
            out = {"error": f"{type(e).__name__}: {e}"}
        self.calls.append({"tool": name, "args": args, "result": out})
        return out


# ------------------------------------------------------------------ language + grounding
_LANG_HINTS = {
    "es": r"\b(qué|que|cómo|como|cuánto|dinero|ahorro|máster|puedo|quiero|pasa|si|mi|el|la|los)\b",
    "fr": r"\b(qu'|quoi|comment|combien|argent|épargne|je|mon|ma|est-ce|si|le|la|les|pourquoi)\b",
    "de": r"\b(was|wie|wieviel|geld|ich|mein|wenn|ist|der|die|das|warum)\b",
}


def detect_language(text: str, hint: str | None = None) -> str:
    if hint:
        return hint[:2].lower()
    t = text.lower()
    scores = {k: len(re.findall(p, t)) for k, p in _LANG_HINTS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "en"


_NUM = re.compile(r"(?<![\w.])-?\d[\d'’,  ]*(?:\.\d+)?\s*(?:k\b)?", re.I)


def _numbers_in(obj: Any, acc: list[float]) -> list[float]:
    if isinstance(obj, bool) or obj is None:
        return acc
    if isinstance(obj, (int, float)):
        acc.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers_in(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numbers_in(v, acc)
    elif isinstance(obj, str):
        for tok in _NUM.findall(obj):
            v = _parse(tok)
            if v is not None:
                acc.append(v)
    return acc


def _parse(tok: str) -> float | None:
    t = tok.strip().lower()
    if re.fullmatch(r"-?0,\d+", t):  # decimal comma (fr/es/de): 0,777
        t = t.replace(",", ".")
    k = t.endswith("k")
    t = re.sub(r"[\s'’, k]", "", t)
    try:
        v = float(t)
    except ValueError:
        return None
    return v * 1000 if k else v


def check_grounding(answer: str, tool_outputs: list[Any], user_text: str = "") -> dict:
    """Every number >= 100 in the answer must match a tool number or one the user said
    (tolerating rounding and probabilities written as percent)."""
    known = _numbers_in(tool_outputs, []) + _numbers_in(user_text, [])
    known += [abs(x) for x in known] + [x * 100 for x in known if abs(x) <= 1]  # probabilities as %
    ungrounded = []
    for tok in _NUM.findall(answer):
        v = _parse(tok)
        if v is None or abs(v) < 100 or (1900 <= v <= 2100 and float(v).is_integer()):
            continue  # small counts, months, option ids and calendar years are not money figures
        if not any(abs(abs(v) - abs(k)) <= max(0.02 * abs(k), 1.0) for k in known):
            ungrounded.append(tok.strip())
    return {"grounded": not ungrounded, "ungrounded_numbers": ungrounded}


# ------------------------------------------------------------------ templates (plan B)
# Exploration wording (plan.md, UBS feedback): "if... then... under these assumptions", never a forecast.
_T = {
    "en": {
        "main": "If you take “{label}”, then under these assumptions your net worth after {years} years would be CHF {nw}. ",
        "neg": "On this path cash would drop below zero in month {m} (lowest CHF {min}), so it would need extra funding. ",
        "noneg": "On this path cash would never drop below zero (lowest CHF {min}). ",
        "lever": "The lever that changes this most is {a}: across its range, final net worth moves by CHF {d}. ",
        "lens": "With the uncertainty lens on, simulated paths end between CHF {p10} and CHF {p90}. ",
        "end": "This is an if-then exploration, not a prediction; change any assumption to see another world. (node {node}, trace {trace})",
    },
    "es": {
        "main": "Si eliges «{label}», con estos supuestos tu patrimonio a {years} años sería CHF {nw}. ",
        "neg": "En este camino la caja bajaría de cero en el mes {m} (mínimo CHF {min}), así que haría falta financiación extra. ",
        "noneg": "En este camino la caja nunca bajaría de cero (mínimo CHF {min}). ",
        "lever": "La palanca que más lo cambia es {a}: en su rango, el patrimonio final se mueve CHF {d}. ",
        "lens": "Con la lente de incertidumbre, los caminos simulados terminan entre CHF {p10} y CHF {p90}. ",
        "end": "Es una exploración si-entonces, no una predicción; cambia cualquier supuesto para ver otro mundo. (nodo {node}, traza {trace})",
    },
    "fr": {
        "main": "Si tu choisis « {label} », alors avec ces hypothèses ton patrimoine après {years} ans serait de CHF {nw}. ",
        "neg": "Sur ce chemin la trésorerie passerait sous zéro au mois {m} (minimum CHF {min}) : il faudrait un financement supplémentaire. ",
        "noneg": "Sur ce chemin la trésorerie ne passerait jamais sous zéro (minimum CHF {min}). ",
        "lever": "Le levier qui change le plus le résultat est {a} : sur sa plage, le patrimoine final varie de CHF {d}. ",
        "lens": "Avec la lentille d'incertitude, les chemins simulés finissent entre CHF {p10} et CHF {p90}. ",
        "end": "C'est une exploration si-alors, pas une prédiction ; change une hypothèse pour voir un autre monde. (nœud {node}, trace {trace})",
    },
}


def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", "'")


def template_answer(ctx: dict, lang: str, box: Toolbox) -> str:
    t = _T.get(lang, _T["en"])
    node_id = ctx.get("node_id") or (ctx.get("path") or ["0"])[-1]
    s = box.get_node(node_id)
    txt = t["main"].format(label=s["label"], years=(s.get("horizon_months") or 120) // 12, nw=_fmt(s["final_net_worth"]))
    txt += t["neg"].format(m=s["first_negative_month"], min=_fmt(s["min_cash"])) if s["first_negative_month"] else \
        t["noneg"].format(min=_fmt(s["min_cash"]))
    top = (s.get("levers") or [{}])[0]
    if top.get("delta_final_net_worth") is not None:
        txt += t["lever"].format(a=top.get("label") or top["assumption_id"], d=_fmt(abs(top["delta_final_net_worth"])))
    lens = s.get("uncertainty_lens")
    if lens:
        txt += t["lens"].format(p10=_fmt(lens["final_net_worth_p10"]), p90=_fmt(lens["final_net_worth_p90"]))
    txt += t["end"].format(node=s["node_id"], trace=s["trace_id"])
    return txt


# Deterministic forecast-language guard (English; the prompt covers other languages).
_FORECAST = [
    (re.compile(r"\byou will\b", re.I), "you would"),
    (re.compile(r"\byou'll\b", re.I), "you would"),
    (re.compile(r"\bwill be\b", re.I), "would be"),
    (re.compile(r"\bwill (have|reach|run|go|end|drop|fall|grow|need|get|hit)\b", re.I), r"would \1"),
    (re.compile(r"\b(is|are) expected to\b", re.I), "would"),
    (re.compile(r"\b(is|are) likely to\b", re.I), "would"),
]


def soften_forecasts(text: str) -> tuple[str, int]:
    n = 0
    for pat, rep in _FORECAST:
        text, k = pat.subn(rep, text)
        n += k
    return text, n


# ------------------------------------------------------------------ LLM loop
SYSTEM = """You are {name}, a small friendly guide who lives in the user's "tree of life" financial explorer.
The explorer shows deterministic "if this, then that" worlds, each with visible, editable assumptions. It does not predict.
Hard rules:
1. NEVER calculate, estimate or invent any number. Every figure you say must be copied from a tool result.
   If you need a number, call a tool. If no tool gives it, say you don't have it.
2. NEVER recommend, advise or decide ("you should", "the best option"). Explain possibilities and trade-offs;
   the user decides.
3. Cite where numbers come from: the node (e.g. "option 1.2") and the key assumptions (levers) involved.
4. Talk in if-then terms: "if you take X, then under these assumptions Y would…". NEVER say "you will", "expected",
   "likely", "chance" or "probability" about the future. {lens_rule}
5. For "what would have to be true" questions (break-even, what salary or saving would be needed, what breaks the
   plan, what if I decide later), first read `exploration` in the loaded results or call get_exploration; if it does
   not answer, call what_would_have_to_be_true. Report the threshold and the lever.
6. Answer in {lang_name}. Plain words, at most {max_sentences} short sentences, no markdown, no lists: it will be read aloud.
   Money as "CHF 12'300". Say months as "month 7".{call_rule}
Context: the user's current node is {node_id}; visible path {path}; active stress what-ifs (weather) {weather}.
Node ids: "0" today; "1","2","3" first decisions; "1.2" = option 2 under option 1, and so on.
Engine results already loaded for the current node, its siblings and its children (the next decisions). Use these
directly; call tools only for other nodes, comparisons you cannot read here, assumption details, what-ifs or
what-would-have-to-be-true searches:
{preloaded}"""

LENS_OFF = "The uncertainty lens is off: do not talk about percentiles or shares of simulated paths."
LENS_ON = ("The user turned on the uncertainty lens: you may mention the spread across simulated paths "
           "(uncertainty_lens), always as 'under these assumptions, X% of simulated paths…', never as a forecast.")


CALL_MAX_SENTENCES = 2
CALL_RULE = ("\n7. This is a live phone call: the first sentence must be under 12 words and give the key fact; "
             "do not repeat the question.")

# Deterministic no-recommendation guard (rule 2 is also in the prompt, this enforces it).
_ADVICE = re.compile(
    r"\b(you should|you might (want to )?consider|i (would )?(recommend|suggest|advise)|my (advice|recommendation)|"
    r"the best (option|choice|path)|it would be (better|wise)|go for|deberías|te recomiendo|te aconsejo|"
    r"la mejor opción|tu devrais|je (te |vous )?(recommande|conseille)|la meilleure option|du solltest|ich empfehle)\b",
    re.I)


def strip_advice(text: str) -> tuple[str, list[str]]:
    """Drop sentences that recommend or decide. Returns (clean text, removed sentences)."""
    sents = split_sentences(text)
    keep = [s for s in sents if not _ADVICE.search(s)]
    removed = [s for s in sents if _ADVICE.search(s)]
    return " ".join(keep).strip(), removed


def split_sentences(text: str) -> list[str]:
    from api.tts_local import split_sentences as _split
    return _split(text, max_chars=10_000)


_LANG_NAMES = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian"}


def llm_status() -> dict:
    return {"available": llm.available(), "models": llm.models()}


def ask(question: str, ctx: dict) -> dict:
    box = Toolbox(ctx)
    lang = detect_language(question, ctx.get("language"))
    node_id = ctx.get("node_id") or (ctx.get("path") or ["0"])[-1]
    cost = 0.0
    tokens = {"prompt": 0, "completion": 0}
    used_model = None
    answer, mode, error = None, "llm", None

    if llm.available():
        preloaded = box.preload(node_id)
        sysmsg = SYSTEM.format(name=ctx.get("character_name", CHARACTER), lang_name=_LANG_NAMES.get(lang, lang),
                               max_sentences=CALL_MAX_SENTENCES if ctx.get("mode") == "call" else 3,
                               call_rule=CALL_RULE if ctx.get("mode") == "call" else "",
                               lens_rule=LENS_ON if ctx.get("uncertainty") else LENS_OFF,
                               node_id=node_id, path=ctx.get("path") or ["0"], weather=ctx.get("weather") or "none",
                               preloaded=json.dumps(preloaded, ensure_ascii=False))
        msgs: list[dict] = [{"role": "system", "content": sysmsg}]
        for h in (ctx.get("history") or [])[-6:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                msgs.append({"role": h["role"], "content": str(h["content"])[:1000]})
        msgs.append({"role": "user", "content": question})
        try:
            for rnd in range(MAX_ROUNDS):
                last = rnd == MAX_ROUNDS - 1
                r = llm.chat(msgs, tools=TOOLS, model=used_model, purpose="agent", temperature=0.2, max_tokens=250,
                             reasoning={"enabled": False}, **({"tool_choice": "none"} if last else {}))
                used_model = r["model"]  # stick to the model that answered
                cost += r["cost_usd"]
                tokens["prompt"] += r["prompt_tokens"]
                tokens["completion"] += r["completion_tokens"]
                msg = r["message"]
                calls = msg.get("tool_calls") or []
                if not calls:
                    answer = re.sub(r"[*_#`]+", "", msg.get("content") or "").strip()
                    break
                msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
                for c in calls:
                    try:
                        args = json.loads(c["function"].get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    out = box.run(c["function"]["name"], args)
                    msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(out)})
        except Exception as e:  # noqa: BLE001
            log.warning("agent llm failed: %s", e)
            error = str(e)[:200]
            answer = None

    grounding = {"grounded": None, "ungrounded_numbers": []}
    removed: list[str] = []
    softened = 0
    if answer:
        answer, removed = strip_advice(answer)
        answer, softened = soften_forecasts(answer)
        if ctx.get("mode") == "call":
            answer = " ".join(split_sentences(answer)[:CALL_MAX_SENTENCES])
    if answer:
        grounding = check_grounding(answer, [c["result"] for c in box.calls], question)
        if not grounding["grounded"]:
            log.warning("ungrounded numbers %s -> template", grounding["ungrounded_numbers"])
            answer = None
    if not answer:
        mode = "template"
        answer = template_answer(ctx, lang, box)
        if grounding["grounded"] is None:
            grounding = {"grounded": True, "ungrounded_numbers": []}

    return {
        "answer": answer,
        "language": lang,
        "mode": mode,  # "llm" or "template" (plan B)
        "grounding": grounding,
        "advice_removed": removed,  # sentences dropped by the no-recommendation guard
        "forecast_phrases_softened": softened,  # "you will" -> "you would" etc.
        "tool_traces": [{"tool": c["tool"], "args": c["args"],
                         "trace_id": c["result"].get("trace_id") or c["result"].get("after", {}).get("trace_id"),
                         "node_id": c["result"].get("node_id")} for c in box.calls],
        "cited_nodes": sorted({c["result"].get("node_id") for c in box.calls if c["result"].get("node_id")}),
        "cost_usd": round(cost, 6),
        "tokens": tokens,
        "model": used_model or "template",
        "error": error,
    }
