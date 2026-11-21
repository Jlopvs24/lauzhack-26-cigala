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
CHARACTER = "Sprout"  # placeholder: character name is OPEN (thread 4)


# ------------------------------------------------------------------ tools
TOOLS = [
    {"type": "function", "function": {
        "name": "get_node",
        "description": "Simulation summary of one decision node (metrics, health, checks, top sensitivities, "
                       "assumptions used, trace id). Node '0' is today with no decision.",
        "parameters": {"type": "object", "properties": {"node_id": {"type": "string"}}, "required": ["node_id"]}}},
    {"type": "function", "function": {
        "name": "compare_nodes",
        "description": "Side-by-side metrics of several nodes (e.g. siblings) with differences vs the first one.",
        "parameters": {"type": "object", "properties": {
            "node_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["node_ids"]}}},
    {"type": "function", "function": {
        "name": "what_if",
        "description": "Re-run a node with one assumption changed (e.g. salary, market return) and return "
                       "the change in metrics. Use get_assumptions to see ids.",
        "parameters": {"type": "object", "properties": {
            "node_id": {"type": "string"}, "assumption_id": {"type": "string"}, "value": {"type": "number"}},
            "required": ["node_id", "assumption_id", "value"]}}},
    {"type": "function", "function": {
        "name": "get_assumptions",
        "description": "All editable assumptions with value, unit and source.",
        "parameters": {"type": "object", "properties": {}}}},
]


def _summary(res: dict, node: dict) -> dict:
    m = res["metrics"]
    fnm = m.get("first_negative_month")
    p = res["bands"]["net_worth"]
    return {
        "node_id": res["node_id"], "label": node.get("label"), "trace_id": res["trace_id"],
        "engine": res.get("engine"), "weather": res.get("weather", []),
        "final_net_worth_p10": p["p10"][-1], "final_net_worth_p50": p["p50"][-1], "final_net_worth_p90": p["p90"][-1],
        "final_cash_deterministic": res["deterministic"]["cash"][-1],
        "min_cash": m["min_cash"],
        "first_negative_month": None if fnm is None else fnm + 1,  # 1-indexed for humans
        "goal_probability": m.get("goal_probability", {}),
        "liquidity_months": m.get("liquidity_months"),
        "health_score": res["health"]["score"], "health_components": res["health"]["components"],
        "top_sensitivities": res.get("sensitivity", [])[:3],
        "checks_passed": all(c["passed"] for c in res.get("checks", [])),
        "assumptions_used": node.get("assumptions_ref", []),
        "interventions": node.get("interventions", []),
        "horizon_months": res.get("horizon_months"), "n_paths": res.get("n_paths"),
    }


class Toolbox:
    def __init__(self, ctx: dict):
        self.profile = ctx["profile"]
        self.overrides = ctx.get("assumptions") or []
        self.weather = ctx.get("weather") or []
        self.cache: dict[str, dict] = {}
        self.calls: list[dict] = []

    def _node(self, node_id: str, overrides=None) -> tuple[dict, dict]:
        node = engine.node_info(node_id)
        key = node_id + json.dumps(overrides or [], sort_keys=True)
        if key not in self.cache:
            self.cache[key] = engine.simulate(self.profile, {"node_id": node_id},
                                              overrides if overrides is not None else self.overrides, self.weather)
        return self.cache[key], node

    def get_node(self, node_id: str) -> dict:
        res, node = self._node(str(node_id))
        out = _summary(res, node)
        vals = {a["id"]: a for a in engine.assumptions(self.overrides)}
        out["assumption_values"] = {i: {"value": vals[i]["value"], "unit": vals[i]["unit"]}
                                    for i in out["assumptions_used"] if i in vals}
        return out

    def compare_nodes(self, node_ids: list[str]) -> dict:
        rows = [self.get_node(n) for n in node_ids]
        base = rows[0]
        diffs = {r["node_id"]: {
            "final_net_worth_p50_minus_first": round(r["final_net_worth_p50"] - base["final_net_worth_p50"], 2),
            "min_cash_minus_first": round(r["min_cash"] - base["min_cash"], 2)} for r in rows[1:]}
        return {"nodes": rows, "differences_vs_first": diffs}

    def what_if(self, node_id: str, assumption_id: str, value: float) -> dict:
        ids = {a["id"] for a in engine.assumptions()}
        if assumption_id not in ids:
            return {"error": f"unknown assumption {assumption_id}", "valid_ids": sorted(ids)}
        before = self.get_node(node_id)
        ov = [o for o in self.overrides if o.get("id") != assumption_id] + [{"id": assumption_id, "value": value}]
        res, node = self._node(str(node_id), ov)
        after = _summary(res, node)
        return {"assumption_id": assumption_id, "new_value": value, "before": before, "after": after,
                "delta_final_net_worth_p50": round(after["final_net_worth_p50"] - before["final_net_worth_p50"], 2),
                "delta_min_cash": round(after["min_cash"] - before["min_cash"], 2)}

    def preload(self, node_id: str) -> list[dict]:
        """Current node + siblings, computed by the engine (free) so most questions need one LLM call.
        Recorded as a tool call so grounding and traces include it."""
        from api.mock_engine import children_ids, parent_of
        par = parent_of(node_id)
        siblings = [s for s in children_ids(par) if s != node_id] if par is not None else []
        ids = [node_id] + siblings + children_ids(node_id)
        rows = []
        for i in ids:
            try:
                rows.append(self.get_node(i))
            except Exception:  # noqa: BLE001
                pass
        self.calls.append({"tool": "preload", "args": {"node_ids": ids}, "result": {"nodes": rows}})
        return rows

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
_T = {
    "en": {
        "main": "{label}: after {years} years the median net worth is CHF {p50} (10–90% range CHF {p10} to CHF {p90}). ",
        "neg": "Cash goes below zero in month {m}, so this path needs extra funding. ",
        "noneg": "Cash never goes below zero (lowest point CHF {min}). ",
        "sens": "The assumption that moves the result most is {a}: +10% changes final net worth by CHF {d}. ",
        "end": "These are conditional simulations, not forecasts; you decide which trade-off fits you. (node {node}, trace {trace})",
    },
    "es": {
        "main": "{label}: a {years} años el patrimonio mediano es CHF {p50} (rango 10–90%: CHF {p10} a CHF {p90}). ",
        "neg": "La caja cae por debajo de cero en el mes {m}: este camino necesita financiación extra. ",
        "noneg": "La caja nunca baja de cero (punto más bajo CHF {min}). ",
        "sens": "El supuesto que más mueve el resultado es {a}: +10% cambia el patrimonio final en CHF {d}. ",
        "end": "Son simulaciones condicionales, no previsiones; tú decides qué equilibrio te encaja. (nodo {node}, traza {trace})",
    },
    "fr": {
        "main": "{label} : après {years} ans, le patrimoine médian est de CHF {p50} (fourchette 10–90 % : CHF {p10} à CHF {p90}). ",
        "neg": "La trésorerie passe sous zéro au mois {m} : ce chemin demande un financement supplémentaire. ",
        "noneg": "La trésorerie ne passe jamais sous zéro (point le plus bas CHF {min}). ",
        "sens": "L'hypothèse qui pèse le plus est {a} : +10 % change le patrimoine final de CHF {d}. ",
        "end": "Ce sont des simulations conditionnelles, pas des prévisions ; c'est toi qui choisis le compromis. (nœud {node}, trace {trace})",
    },
}


def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", "'")


def template_answer(ctx: dict, lang: str, box: Toolbox) -> str:
    t = _T.get(lang, _T["en"])
    node_id = ctx.get("node_id") or (ctx.get("path") or ["0"])[-1]
    s = box.get_node(node_id)
    txt = t["main"].format(label=s["label"], years=s["horizon_months"] // 12, p50=_fmt(s["final_net_worth_p50"]),
                           p10=_fmt(s["final_net_worth_p10"]), p90=_fmt(s["final_net_worth_p90"]))
    txt += t["neg"].format(m=s["first_negative_month"]) if s["first_negative_month"] else \
        t["noneg"].format(min=_fmt(s["min_cash"]))
    if s["top_sensitivities"]:
        top = s["top_sensitivities"][0]
        txt += t["sens"].format(a=top["assumption_id"], d=_fmt(top["delta_final_net_worth"]))
    txt += t["end"].format(node=s["node_id"], trace=s["trace_id"])
    return txt


# ------------------------------------------------------------------ LLM loop
SYSTEM = """You are {name}, a small friendly sprout who lives in the user's "tree of life" financial simulator.
Hard rules:
1. NEVER calculate, estimate or invent any number. Every figure you say must be copied from a tool result.
   If you need a number, call a tool. If no tool gives it, say you don't have it.
2. NEVER recommend, advise or decide ("you should", "the best option"). Explain possibilities and trade-offs;
   the user decides.
3. Cite where numbers come from: the node (e.g. "option 1.2") and the key assumption ids involved.
4. Results are conditional simulations, not forecasts. Mention uncertainty (the 10–90% range) when relevant.
5. Answer in {lang_name}. Plain words, at most 3 short sentences, no markdown, no lists: it will be read aloud.
   Money as "CHF 12'300". Say months as "month 7".
Context: the user's current node is {node_id}; visible path {path}; active weather {weather}.
Node ids: "0" today; "1","2","3" first decisions; "1.2" = option 2 under option 1, and so on.
Engine results already loaded for the current node, its siblings and its children (the next decisions) (use these directly, call tools only
for other nodes, comparisons you cannot read here, assumption details or what-if changes):
{preloaded}"""

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
        "tool_traces": [{"tool": c["tool"], "args": c["args"],
                         "trace_id": c["result"].get("trace_id") or c["result"].get("after", {}).get("trace_id"),
                         "node_id": c["result"].get("node_id")} for c in box.calls],
        "cited_nodes": sorted({c["result"].get("node_id") for c in box.calls if c["result"].get("node_id")}),
        "cost_usd": round(cost, 6),
        "tokens": tokens,
        "model": used_model or "template",
        "error": error,
    }
