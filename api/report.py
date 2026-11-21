"""Path report (docs/report-spec.md §3): POST /report {profile, path, assumptions}.

Aggregates engine results for every step of the chosen path into 12 structured sections.
No number here is produced by an LLM. Engine fields that core/ adds later (result.headline,
result.constraints, per-step exploration, stress side-by-side) are used when present; until
then the equivalents are derived here from deterministic engine outputs and marked
`"derived_by": "api"`.
The plain-language summary may use the LLM, but every number in it must pass the grounding
check against this report's data; otherwise the template summary is used.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api import agent, engine, llm

REPORT_VERSION = "report-1.0"
WEATHER_TYPES = ["recession", "inflation", "market_crash", "job_loss"]

SECTION_ORDER = [
    ("summary", "Plain-language summary"),
    ("scope", "Question and scope"),
    ("starting_state", "Starting state"),
    ("decisions", "Decisions on this path"),
    ("alternatives", "Baseline and alternatives at every level"),
    ("exploration", "What would have to be true (exploration per step)"),
    ("stress", "Stress scenarios"),
    ("constraints", "Constraints and breaches"),
    ("tradeoffs", "Non-financial trade-offs"),
    ("uncertainty", "Uncertainty lens (optional)"),
    ("validation", "Validation and reproducibility"),
    ("limitations", "Limitations and responsible AI"),
]


# ------------------------------------------------------------------ helpers
def _m1(m):
    return None if m is None else m + 1  # engine months are 0-based; people say "month 7"


def _metrics(res: dict) -> dict:
    """Deterministic headline metrics of one result (never reads bands)."""
    m = res.get("metrics") or {}
    d = agent._det(res)
    goals = res.get("goals") or []
    return {
        "final_net_worth": d["final_net_worth"],
        "final_net_worth_real": m.get("final_net_worth_real"),
        "final_cash": d["final_cash"],
        "min_cash": d["min_cash"],
        "min_cash_month": d["min_cash_month"],
        "first_negative_month": d["first_negative_month"],
        "final_debt": m.get("final_debt"),
        "liquidity_months": m.get("liquidity_months"),
        "goals_met": sum(1 for g in goals if g.get("met_deterministic")),
        "goals_total": len(goals),
        "plan_check": (res.get("health") or {}).get("level"),
        "trace_id": res.get("trace_id"),
    }


def _node_row(n: dict) -> dict:
    return {"node_id": n["node_id"], "label": n.get("label"), "status": n.get("status"), **_metrics(n["result"])}


def _source_label(src: str | None) -> str:
    s = (src or "").lower()
    if any(k in s for k in ("ocr", "pdf", "payslip", "statement", "contract", "document")):
        return "observed (document)"
    if any(k in s for k in ("questionnaire", "voice", "text", "user", "edit")):
        return "user-entered"
    if "ubs_kit" in s or "synthetic" in s or "fixture" in s:
        return "synthetic"
    if "assumption" in s:
        return "assumption"
    return "unknown"


# ------------------------------------------------------------------ sections
def _scope(profile: dict, leaf_res: dict, path_nodes: list[dict]) -> dict:
    return {
        "question": "If " + " then ".join(f"“{n['label']}”" for n in path_nodes[1:]) +
                    ", what would follow under the stated assumptions?" if len(path_nodes) > 1
        else "What follows if nothing changes, under the stated assumptions?",
        "person": profile.get("display_name"),
        "horizon_months": leaf_res.get("horizon_months"),
        "currency": leaf_res.get("currency") or profile.get("currency", "CHF"),
        "jurisdiction": "Switzerland (" + str(profile.get("city") or "CH") + ")",
        "as_of": leaf_res.get("as_of") or profile.get("as_of"),
        "values": "nominal CHF; final_net_worth_real is in today's prices",
        "basis": "deterministic if-then paths; not a forecast, not advice",
    }


def _starting_state(profile: dict, demo: bool = False) -> dict:
    prov = profile.get("provenance") or {}
    fields = ["cash", "monthly_net_income", "monthly_rent", "monthly_other_expenses",
              "monthly_investment_contribution", "employment_status", "age", "city"]
    rows = []
    for f in fields:
        if f not in profile:
            continue
        p = prov.get(f) or {}
        rows.append({"field": f, "value": profile[f], "source": p.get("source") or ("demo profile" if demo else None),
                     "label": _source_label(p.get("source")) if p else ("synthetic" if demo else "unknown"),
                     "confidence": p.get("confidence")})
    goals = profile.get("goals") or []
    return {"profile_id": profile.get("profile_id"), "display_name": profile.get("display_name"),
            "fields": rows, "assets": profile.get("assets") or [], "liabilities": profile.get("liabilities") or [],
            "goals": goals, "goals_source": _source_label((prov.get("goals") or {}).get("source"))}


def _decisions(steps: list[dict], assumptions: dict) -> list[dict]:
    out = []
    for st in steps:
        n, res = st["node"], st["node"]["result"]
        introduced = sorted(set(n.get("assumptions_ref") or []) |
                            {a.get("id") for a in res.get("assumptions_used") or [] if a.get("set_by_decision") == n["node_id"]})
        out.append({
            "step": st["depth"], "node_id": n["node_id"], "label": n.get("label"),
            "description": n.get("description"), "changes": n.get("changes") or [],
            "interventions": n.get("interventions") or [], "ubs_catalog": n.get("catalog") or [],
            "assumptions_introduced": [{k: assumptions[a].get(k) for k in
                                        ("id", "label", "value", "unit", "kind", "source", "verified")}
                                       for a in introduced if a in assumptions],
            "delta_vs_parent": n.get("delta_vs_parent"),
            "events": res.get("events") or [], "debts": res.get("debts") or [],
            "headline": res.get("headline") or _headline(res),
        })
    return out


def _headline(res: dict) -> dict:
    """Slot A of the branch card (spec §1), derived until core ships result.headline."""
    m = _metrics(res)
    missed = [g for g in res.get("goals") or [] if g.get("met_deterministic") is False]
    if m["first_negative_month"] is not None:
        a = f"Funding gap CHF {abs(m['min_cash']):,.0f} from month {m['first_negative_month']}".replace(",", "'")
    elif missed:
        g = missed[0]
        gap = (g.get("target") or 0) - (g.get("deterministic_value") or 0)
        a = f"{g.get('name')} missed by CHF {gap:,.0f}".replace(",", "'")
    else:
        a = f"Tightest buffer: {m['liquidity_months']} months" if m["liquidity_months"] is not None else "Holds"
    return {"slot_a": a, "derived_by": "api"}


def _alternatives(steps: list[dict], root: dict | None) -> dict:
    levels = []
    for st in steps:
        levels.append({"step": st["depth"], "chosen": _node_row(st["node"]),
                       "siblings": [_node_row(s) for s in st["siblings"]]})
    return {"status_quo_baseline": _node_row(root) if root else None, "levels": levels,
            "reading": "each row is a deterministic if-then path under the same assumptions"}


def _exploration(steps: list[dict]) -> list[dict]:
    out = []
    for st in steps:
        res = st["node"]["result"]
        expl = res.get("exploration")
        out.append({"step": st["depth"], "node_id": st["node"]["node_id"], "label": st["node"].get("label"),
                    "facts": [f["text"] for f in agent.exploration_facts(expl, st["node"].get("label"))],
                    "exploration": expl, "tornado": res.get("sensitivity") or []})
    return out


def _stress(profile, leaf_id, overrides) -> dict:
    rows = []
    for w in [None] + WEATHER_TYPES:
        res = engine.simulate(profile, {"node_id": leaf_id}, overrides, [w] if w else [], fast=True)
        meta = (res.get("weather") or [{}])[0] if w else {}
        rows.append({"weather": w or "none", "label": (meta.get("label") if isinstance(meta, dict) else None) or w
                     or "No stress", **{k: v for k, v in _metrics(res).items() if k != "trace_id"},
                     "trace_id": res.get("trace_id")})
    holds = [r["weather"] for r in rows[1:] if r["first_negative_month"] is None and r["goals_met"] == r["goals_total"]]
    return {"node_id": leaf_id, "rows": rows, "holds_in": holds,
            "summary": f"holds in {len(holds)} of {len(WEATHER_TYPES)} stress scenarios",
            "reading": "named deterministic what-ifs, not probabilities", "derived_by": "api"}


def _constraints(res: dict, assumptions: dict) -> dict:
    if res.get("constraints"):
        return {"items": res["constraints"], "derived_by": "core"}
    d = res.get("deterministic") or {}
    cash = d.get("cash") or []
    flows = d.get("flows") or {}
    H = res.get("horizon_months") or max(len(cash) - 1, 1)
    gap_months = sum(1 for c in cash[1:] if c < -0.01)
    items = [{
        "name": "liquidity_floor", "threshold": "cash >= CHF 0", "defined_by": "scenario",
        "passed": gap_months == 0, "margin": (res.get("metrics") or {}).get("min_cash"),
        "first_breach_month": _m1((res.get("metrics") or {}).get("first_negative_month")),
        "months_in_breach": gap_months}]
    inc, pay = flows.get("income") or [], flows.get("debt_payment") or []
    if inc and pay:
        ratios = [p / i for p, i in zip(pay, inc) if i > 0]
        limit = next((a["value"] for a in assumptions.values() if "debt" in (a.get("param") or "")
                      and "service" in (a.get("param") or "")), 0.35)
        worst = max(ratios) if ratios else 0.0
        items.append({"name": "debt_service", "threshold": f"debt payments / income <= {limit}",
                      "defined_by": "assumption", "passed": worst <= limit, "margin": round(limit - worst, 4),
                      "worst_ratio": round(worst, 4),
                      "months_in_breach": sum(1 for r in ratios if r > limit)})
    for g in res.get("goals") or []:
        items.append({"name": f"goal: {g.get('name')}", "threshold": f"{g.get('target')} by month {_m1(g.get('target_month'))}",
                      "defined_by": "user", "passed": bool(g.get("met_deterministic")),
                      "margin": None if g.get("deterministic_value") is None or g.get("target") is None
                      else round(g["deterministic_value"] - g["target"], 2)})
    surplus = None
    if inc:
        keys = ("income", "one_off_income", "loan_proceeds", "cash_interest")
        minus = ("income_tax", "living_expenses", "one_off_cost", "debt_payment")
        tot = sum(sum(flows.get(k) or []) for k in keys) - sum(sum(flows.get(k) or []) for k in minus)
        surplus = round(tot / H, 2)
    return {"items": items, "funding_gap_months": gap_months, "average_monthly_surplus": surplus,
            "derived_by": "api"}


_TRADEOFFS = [
    (r"master|stud(y|ies)|degree|course|university|phd", "education",
     "builds qualifications; delays full-time earnings"),
    (r"abroad|move|relocat|country|come back", "location",
     "new place and network; distance from current support"),
    (r"start working|full.?time|take the job|first job", "time",
     "earns sooner; less time for further study"),
    (r"\d+ ?%|part.?time|student job", "time",
     "more income now; less time for studies or rest"),
    (r"loan|credit|borrow|debt", "obligations",
     "more cash now; fixed repayments later reduce flexibility"),
    (r"share|flat ?mate|room ?mate|shared", "lifestyle",
     "lower costs; less privacy"),
    (r"invest|etf|fund|sav(e|ing)", "security",
     "builds a buffer; money is less available for other uses"),
    (r"car|buy", "lifestyle",
     "more convenience; higher fixed costs"),
]


def _tradeoffs(steps: list[dict]) -> dict:
    out = []
    for st in steps:
        n = st["node"]
        text = (n.get("label") or "").lower()
        dims = [{"dimension": d, "note": note} for pat, d, note in _TRADEOFFS if re.search(pat, text)]
        out.append({"node_id": n["node_id"], "label": n.get("label"), "dimensions": dims})
    return {"items": out, "reading": "qualitative, not computed by the engine; the user weighs them"}


def _uncertainty(profile, leaf_id, overrides, want: bool) -> dict:
    if not want:
        return {"enabled": False, "reading": "off by default; ask with uncertainty=true"}
    res = engine.simulate(profile, {"node_id": leaf_id}, overrides, [], uncertainty=True)
    m = res.get("metrics") or {}
    return {"enabled": True, "seed": res.get("seed"), "n_paths": res.get("n_paths"),
            "final_net_worth_p10": m.get("final_net_worth_p10"), "final_net_worth_p50": m.get("final_net_worth_p50"),
            "final_net_worth_p90": m.get("final_net_worth_p90"),
            "share_of_paths_with_funding_gap": m.get("shortfall_probability"),
            "bands": res.get("bands"),
            "reading": "spread across simulated paths under these assumptions; not real-world probabilities"}


def _test_evidence() -> list[dict]:
    root = Path(__file__).resolve().parent.parent
    out = []
    for f in sorted((root / "core" / "tests").glob("test_*.py")) + sorted((root / "api" / "tests").glob("test_*.py")):
        for name in re.findall(r"^def (test_\w+)", f.read_text(encoding="utf-8"), re.M):
            if re.search(r"isolation|monoton|identity|reproduc|starter|ground|check", name):
                out.append({"file": str(f.relative_to(root)).replace("\\", "/"), "test": name})
    return out


def _validation(leaf_res: dict, body: dict) -> dict:
    return {
        "checks": leaf_res.get("checks") or [],
        "all_checks_passed": all(c.get("passed") for c in leaf_res.get("checks") or []),
        "engine_version": leaf_res.get("engine_version") or leaf_res.get("engine"),
        "seed": leaf_res.get("seed"), "trace_id": leaf_res.get("trace_id"),
        "reproduce": {"route": "POST /report", "body": body},
        "test_evidence": _test_evidence(),
        "reading": "same inputs give the same trace_id and the same numbers",
    }


LIMITATIONS = [
    "Synthetic profile and illustrative assumptions; unverified assumptions are flagged (verified=false).",
    "Simplified Swiss model: one income tax table, fixed-rate loans, one balanced portfolio, no pension pillars "
    "beyond what the profile states.",
    "Deterministic if-then paths, not forecasts. The optional uncertainty lens shows spreads under the same "
    "assumptions, not real-world probabilities.",
    "Not financial advice: the report explains consequences and trade-offs; the user decides.",
    "No number is produced by a language model: every figure comes from the engine. The summary is checked "
    "number by number against this report and replaced by a template if any figure is not found.",
    "Non-financial trade-offs are qualitative notes, not scores.",
]


# ------------------------------------------------------------------ summary
def _template_summary(rep: dict) -> str:
    dec = rep["decisions"]
    leaf = rep["alternatives"]["levels"][-1]["chosen"] if rep["alternatives"]["levels"] else \
        rep["alternatives"]["status_quo_baseline"]
    path_txt = " then ".join(f"“{d['label']}”" for d in dec) or "nothing changes"
    fmt = agent._fmt
    s = (f"If {path_txt}, then under these assumptions final net worth after "
         f"{(rep['scope']['horizon_months'] or 120) // 12} years would be CHF {fmt(leaf['final_net_worth'])}. ")
    if leaf["first_negative_month"] is not None:
        s += (f"Cash would drop below zero in month {leaf['first_negative_month']} (lowest CHF {fmt(leaf['min_cash'])}), "
              f"a funding gap lasting {rep['constraints'].get('funding_gap_months')} months. ")
    else:
        s += f"Cash would stay positive (lowest CHF {fmt(leaf['min_cash'])}). "
    s += f"{leaf['goals_met']} of {leaf['goals_total']} goals would be reached. "
    rows = rep["stress"]["rows"]
    broken = [r["label"] for r in rows[1:] if r["weather"] not in rep["stress"]["holds_in"]]
    base_breaks = rows and (rows[0]["first_negative_month"] is not None or rows[0]["goals_met"] < rows[0]["goals_total"])
    if base_breaks:
        s += "Even without any stress scenario this plan needs extra financing, so it does not hold under stress either. "
    else:
        s += f"The plan {rep['stress']['summary']}" + (f" (it breaks under: {', '.join(broken)})" if broken else "") + ". "
    facts = [f for st in rep["exploration"] for f in st["facts"]]
    pick = next((f for f in facts if "at least" in f), None) or (facts[0] if facts else None)
    if pick:
        s += pick + " "
    return s + "This is an exploration, not a prediction or advice."


def _summary(rep: dict, language: str, template: str | None = None) -> dict:
    template = template or _template_summary(rep)
    if not llm.available():
        return {"text": template, "mode": "template", "cost_usd": 0.0, "model": "template"}
    lang = agent._LANG_NAMES.get(language[:2], "English")
    # The LLM may only reword (or translate) the deterministic template: no new facts, no new numbers.
    msgs = [{"role": "system", "content":
             f"Rewrite the text below in {lang} as a warm, plain-language summary for the person it describes "
             "(second person, 4-6 short sentences, no markdown). Keep every fact and every number exactly as given "
             "(same values, CHF 12'300 style, 'month 7'); do not add, drop, combine or reinterpret facts; keep the "
             "if-then wording ('if…, then under these assumptions… would…'); never recommend, never say 'will' or "
             f"'expected'. Answer only with the rewritten text, in {lang}."},
            {"role": "user", "content": template}]
    try:
        r = llm.chat(msgs, purpose="report", temperature=0.2, max_tokens=300, reasoning={"enabled": False})
    except Exception as e:  # noqa: BLE001
        return {"text": template, "mode": "template", "cost_usd": 0.0, "model": "template", "error": str(e)[:200]}
    text = re.sub(r"[*_#`]+", "", r["message"].get("content") or "").strip()
    text, removed = agent.strip_advice(text)
    text, _ = agent.soften_forecasts(text)
    g = agent.check_grounding(text, [template], rel_tol=0.005)  # only the template's numbers are allowed
    if not text or not g["grounded"]:
        return {"text": template, "mode": "template", "cost_usd": r["cost_usd"], "model": r["model"],
                "rejected_llm_numbers": g["ungrounded_numbers"]}
    return {"text": text, "mode": "llm", "cost_usd": r["cost_usd"], "model": r["model"], "grounding": g,
            "advice_removed": removed, "template": template}


# ------------------------------------------------------------------ thin wrapper over core.report_data (#27)
def _core_report_data():
    core = getattr(engine, "_CORE", None)
    return getattr(core, "report_data", None) if core else None


def _row(node_id, label, summ: dict, headline: dict | None = None, status: str | None = None) -> dict:
    """One alternatives row. Months stay as the engine gives them (0-based)."""
    return {"node_id": node_id, "label": label, "status": status, **(summ or {}),
            "headline": headline}


def _sections_from_core(data: dict, body: dict) -> dict:
    steps = data.get("steps") or []
    q = data.get("question") or {}
    scope = {**q, "basis": "deterministic if-then paths; not a forecast, not advice",
             "question_text": "If " + " then ".join(f"“{s['label']}”" for s in steps) +
                              ", what would follow under the stated assumptions?" if steps
             else "What follows if nothing changes, under the stated assumptions?"}
    decisions = [{
        "step": s.get("depth"), "node_id": s["node_id"], "label": s.get("label"), "description": s.get("description"),
        "changes": s.get("changes") or [], "interventions": s.get("interventions") or [],
        "ubs_catalog": s.get("catalog") or [], "assumptions_introduced": s.get("assumptions_introduced") or [],
        "delta_vs_parent": s.get("delta_vs_parent"), "headline": s.get("headline"),
        "events": (s.get("result") or {}).get("events") or [], "debts": (s.get("result") or {}).get("debts") or [],
    } for s in steps]
    base = data.get("baseline") or {}
    from core.report import summary as core_summary  # type: ignore  # noqa: PLC0415
    levels = [{"step": s.get("depth"),
               "chosen": _row(s["node_id"], s.get("label"), core_summary(s["result"]), s.get("headline"), "chosen"),
               "siblings": [_row(a["node_id"], a.get("label"), a.get("summary"), a.get("headline"), a.get("status"))
                            for a in s.get("alternatives") or []]} for s in steps]
    alternatives = {"status_quo_baseline": _row(base.get("node_id"), base.get("label"), base.get("summary"),
                                                base.get("headline"), "baseline"),
                    "levels": levels, "months": "0-based, as in the engine",
                    "reading": "each row is a deterministic if-then path under the same assumptions"}
    exploration = [{"step": s.get("depth"), "node_id": s["node_id"], "label": s.get("label"),
                    "facts": [f["text"] for f in agent.exploration_facts((s.get("result") or {}).get("exploration"),
                                                                        s.get("label"))],
                    "exploration": (s.get("result") or {}).get("exploration"),
                    "tornado": (s.get("result") or {}).get("sensitivity") or []} for s in steps]
    leaf = data.get("leaf") or {}
    wr = leaf.get("weather_resilience") or {}
    stress_rows = data.get("stress") or []
    stress = {"node_id": leaf.get("node_id"), "rows": stress_rows, "weather_resilience": wr,
              "holds_in": wr.get("holds_in"), "of": wr.get("of"),
              "reading": "named deterministic what-ifs, not probabilities"}
    surplus = leaf.get("monthly_surplus") or []
    constraints = {"items": leaf.get("constraints") or [], "plan_check": leaf.get("plan_check"),
                   "monthly_surplus": surplus,
                   "average_monthly_surplus": round(sum(surplus) / len(surplus), 2) if surplus else None,
                   "funding_gap_months": next((c.get("months_in_breach") for c in leaf.get("constraints") or []
                                               if c.get("name") == "no_funding_gap"), None),
                   "derived_by": "core"}
    unc = data.get("uncertainty")
    uncertainty = {"enabled": True, **unc} if unc else {"enabled": False,
                                                        "reading": "off by default; ask with uncertainty=true"}
    validation = {**(data.get("validation") or {}),
                  "all_checks_passed": all(c.get("passed") for c in (data.get("validation") or {}).get("checks") or []),
                  "reproduce_report": {"route": "POST /report", "body": body}}
    limitations = list(data.get("limitations") or []) + [
        "The summary is a deterministic template; a language model may only reword or translate it, and its text "
        "is rejected if it contains any number that is not in the template."]
    nodes = [{"label": s.get("label"), "description": s.get("description")} for s in steps]
    return {"scope": scope, "starting_state": {"fields": data.get("starting_state") or []},
            "decisions": decisions, "alternatives": alternatives, "exploration": exploration, "stress": stress,
            "constraints": constraints, "tradeoffs": _tradeoffs([{"node": {"node_id": s["node_id"], **n}}
                                                                 for s, n in zip(steps, nodes)]),
            "uncertainty": uncertainty, "validation": validation, "limitations": limitations,
            "_engine_version": data.get("engine_version")}


def _template_from_core(S: dict) -> str:
    fmt = agent._fmt
    lv = S["alternatives"]["levels"]
    leaf = lv[-1]["chosen"] if lv else S["alternatives"]["status_quo_baseline"]
    path_txt = " then ".join(f"“{d['label']}”" for d in S["decisions"]) or "nothing changes"
    years = (S["scope"].get("horizon_months") or 120) // 12
    s = (f"If {path_txt}, then under these assumptions net worth after {years} years would be "
         f"CHF {fmt(leaf['final_net_worth'])}")
    if leaf.get("final_net_worth_real") is not None:
        s += f" (CHF {fmt(leaf['final_net_worth_real'])} in today's prices)"
    s += ". "
    pc = S["constraints"].get("plan_check") or {}
    if pc.get("label"):
        s += f"Plan check: {pc['label']}. "
    if leaf.get("first_negative_month") is not None:
        s += (f"Cash would drop below zero in month {leaf['first_negative_month'] + 1} "
              f"(lowest CHF {fmt(leaf['min_cash'])}). ")
    else:
        s += f"Cash would stay positive (lowest CHF {fmt(leaf['min_cash'])}). "
    s += f"{leaf.get('goals_met')} of {leaf.get('goals_total')} goals would be reached. "
    st = S["stress"]
    if st.get("of"):
        held = st.get("holds_in")
        n_held = len(held) if isinstance(held, list) else held
        s += f"Under the named stress scenarios, the plan holds in {n_held} of {st['of']}. "
    facts = [f for e in S["exploration"] for f in e["facts"]]
    pick = next((f for f in facts if "at least" in f), None) or (facts[0] if facts else None)
    if pick:
        s += pick + " "
    return s + "This is an exploration, not a prediction or advice."


# ------------------------------------------------------------------ build
def _template_only(template: str) -> dict:
    return {"text": template, "mode": "template", "template": template, "cost_usd": 0.0, "model": "template",
            "llm_summary": "POST /report/summary (same body) returns the LLM rewording when it is ready"}


def llm_summary(report: dict, language: str = "en") -> dict:
    """The grounded LLM rewording of a built report's template summary (frugal default model).
    Every number must come from the template, else the template is returned."""
    template = report["sections"]["summary"]["template"]
    return _summary(report["sections"], language, template)


def build_report(profile: dict | None, path: list[str], overrides: list[dict] | None = None,
                 uncertainty: bool = False, language: str = "en", with_llm: bool = False) -> dict:
    """with_llm=False (default): no LLM in the request path; the summary is the deterministic template."""
    t0 = time.perf_counter()
    overrides = overrides or []
    path = [p for p in (path or []) if p and p != "0"]
    body = {"path": path, "assumptions": overrides, "uncertainty": uncertainty}
    report_data = _core_report_data()
    if report_data:  # core >= #27: thin wrapper, every number from core.report_data
        data = report_data(profile, path, overrides, [], uncertainty=uncertainty,
                           **engine._extras_kw(report_data))  # personal conditions, if any
        rep = _sections_from_core(data, body)
        engine_version = rep.pop("_engine_version", None)
        tmpl = _template_from_core(rep)
        summ = _summary(rep, language, tmpl) if with_llm else _template_only(tmpl)
        return {
            "report_version": REPORT_VERSION, "source": "core.report_data", "engine_version": engine_version,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "path": ["0"] + path, "leaf": (data.get("leaf") or {}).get("node_id") or (path[-1] if path else "0"),
            "section_order": [{"key": k, "title": t, "n": i + 1} for i, (k, t) in enumerate(SECTION_ORDER)],
            "sections": {"summary": summ, **rep},
            "cost_usd": round(summ.get("cost_usd", 0.0), 6),
            "latency_ms": int((time.perf_counter() - t0) * 1000), "model": summ.get("model"),
        }
    # fallback (mock engine / older core): derive the same sections from expand + simulate
    demo = not profile
    profile = profile or engine.default_profile()
    steps, root = [], None
    for i in range(len(path)):
        tree = engine.expand(profile, path[: i + 1], overrides, [])
        nodes = [n for n in tree["nodes"] if n.get("result")]
        if root is None:
            root = next((n for n in nodes if n["node_id"] in ("0", tree.get("path", ["0"])[0])), None)
        cur = next(n for n in nodes if n["node_id"] == path[i])
        steps.append({"depth": i + 1, "node": cur, "siblings": [n for n in nodes if n.get("status") == "sibling"]})
    if not steps:
        tree = engine.expand(profile, [], overrides, [])
        root = next(n for n in tree["nodes"] if n["node_id"] == tree["current"])
    leaf = steps[-1]["node"] if steps else root
    leaf_res = leaf["result"]
    assumptions = {a["id"]: a for a in engine.assumptions(overrides)}

    rep: dict[str, Any] = {
        "scope": _scope(profile, leaf_res, [root] + [s["node"] for s in steps]),
        "starting_state": _starting_state(profile, demo),
        "decisions": _decisions(steps, assumptions),
        "alternatives": _alternatives(steps, root),
        "exploration": _exploration(steps),
        "stress": _stress(profile, leaf["node_id"], overrides),
        "constraints": _constraints(leaf_res, assumptions),
        "tradeoffs": _tradeoffs(steps),
        "uncertainty": _uncertainty(profile, leaf["node_id"], overrides, uncertainty),
        "validation": _validation(leaf_res, {"path": path, "assumptions": overrides, "uncertainty": uncertainty}),
        "limitations": LIMITATIONS,
    }
    summ = _summary(rep, language) if with_llm else _template_only(_template_summary(rep))
    rep = {"summary": summ, **rep}
    return {
        "report_version": REPORT_VERSION, "source": "api (derived from expand/simulate)",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "path": ["0"] + path, "leaf": leaf["node_id"],
        "section_order": [{"key": k, "title": t, "n": i + 1} for i, (k, t) in enumerate(SECTION_ORDER)],
        "sections": rep,
        "cost_usd": round(summ.get("cost_usd", 0.0), 6),
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "model": summ.get("model"),
    }
