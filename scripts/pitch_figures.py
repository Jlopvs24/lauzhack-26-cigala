"""Print every figure quoted in README.md, docs/pitch.md and docs/submission/*, straight from the code.

Nothing in those docs should be typed by hand: re-run this before submitting and copy what it prints.

    python scripts/pitch_figures.py              # engine, demo path, personal condition, AXA, IMC (~10 s)
    python scripts/pitch_figures.py --tests      # also runs the test suites and prints pass counts (minutes)
    python scripts/pitch_figures.py --json       # the same figures as JSON

Run from the repository root. Engine figures use Alexia's demo profile and default assumptions,
deterministic path (no Monte Carlo), exactly as the web app requests them.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core  # noqa: E402

# The demo's personal condition: what /tree/personalize returned on Sat 21 Nov for
# "I would get a CHF 600/month scholarship during the master" on node 2 (qwen3.7-flash, 2.5 s, USD 0.00008).
SCHOLARSHIP = {"param": "monthly_net_income", "op": "add", "value": 600, "from_month": 0, "to_month": 24,
               "label": "Scholarship", "source": "user"}
PATCH = {"2": [SCHOLARSHIP]}
NEW_BRANCH = [{"node_id": "2.c1", "parent_id": "2", "label": "Do a master's: Scholarship",
               "description": "Scholarship during master's", "interventions": [SCHOLARSHIP], "custom": True}]
BENCH = ROOT / "multimodal/benchmark/results"
BENCH_RUN, BENCH_REUSED = "20261121-151135", "20261121-145235"   # RESULTS.md: vlm_small / vlm_large reused
LEVEL_EN = {"needs_financing": "Needs financing", "infeasible": "Does not hold: a limit is broken",
            "holds_below_target": "Holds, below the buffer target", "holds": "Holds"}   # web/src/scene/headline.js


def chf(v):
    return "none" if v is None else f"CHF {v:,.0f}".replace("CHF -", "CHF −")


def node_row(n):
    r = n["result"]
    m, pc, hl = r["metrics"], r["plan_check"], r["headline"]
    res = pc.get("resilience") or {}
    gap = hl["slot_a"] if hl["slot_a"]["kind"] == "funding_gap" else None
    return {
        "node_id": n["node_id"], "label": n["label"], "status": n["status"], "custom": bool(n.get("custom")),
        "plan_check": pc["level"], "plan_check_label": pc["label"],
        "final_net_worth_real": m.get("final_net_worth_real"), "final_net_worth": m["final_net_worth"],
        "min_cash": m["min_cash"],
        "funding_gap_chf": gap["value"] if gap else None,
        "funding_gap_from_month": (gap["month"] + 1) if gap else None,   # 1-based, as the UI says it
        "headline_a": hl["slot_a"]["text"], "headline_b": hl["slot_b"]["text"],
        "holds_in_weather": res.get("holds_in_weather"), "weather_of": res.get("of"),
        "shock_buffer_chf": res.get("shock_buffer_chf"),
    }


def expand(path, **kw):
    out = core.expand(None, path, None, None, exploration=False, sensitivity=False, **kw)
    return {n["node_id"]: node_row(n) for n in out["nodes"] if n.get("result")}


def lumi_line(row, desc, kids):
    """Lumi's English bubble for a node (web/src/scene/i18n.js STORY.en + narration.js), from engine fields."""
    lower = lambda s: s[:1].lower() + s[1:]  # noqa: E731
    lst = lambda a: a[0] if len(a) == 1 else ", ".join(a[:-1]) + " or " + a[-1]  # noqa: E731
    fneg = row["funding_gap_from_month"]
    # narration uses metrics.first_negative_month + 1, which equals the funding-gap month when there is one
    cash = f"In this scenario the cash runs short from month {fneg}." if fneg else "In this scenario the cash never runs out."
    check = lower(LEVEL_EN.get(row["plan_check"], row["plan_check_label"]))
    desc = desc if not desc or desc.endswith(".") else desc + "."
    if row["node_id"] == "0":
        return (f"This is Alexia today. {desc} Plan check: {check}. {cash} Three paths grow from here: "
                f"{lst([lower(k) for k in kids])}. Choose one and I'll show you what it changes.")
    tail = f"From here: {lst([lower(k) for k in kids])}." if kids else "This is the end of this branch; open the report for the details."
    return f"{row['label']}. {desc} Plan check: {check}. {cash} {tail} The other branches stay in grey so you can compare."


def tree_nodes():
    idx = {}

    def walk(n):
        idx[n["node_id"]] = n
        for c in n.get("children", []):
            walk(c)
    walk(core.load_tree()["root"])
    return idx


def engine_figures():
    t0 = time.perf_counter()
    val = core.validation()
    nodes = tree_nodes()
    top = expand([])
    master = expand(["2"])
    patched = expand(["2"], node_patches=PATCH)
    branch = expand(["2"], custom_nodes=NEW_BRANCH)
    leaf_path = ["2", "2.2", "2.2.1"]
    leaf = expand(leaf_path, node_patches=PATCH)

    ex = core.explore(None, ["2"])["exploration"]
    ex_p = core.explore(None, ["2"], node_patches=PATCH)["exploration"]

    def be(e):
        return {r["compared_to"]: r["salary_threshold"].get("value") for r in e["break_even"]}

    p3a = core.explore(None, ["1"])["exploration"].get("pillar_3a") or {}
    rep = core.report_data(None, leaf_path, node_patches=PATCH)
    stress = [{"weather": s["weather"], "plan_check": s["summary"].get("plan_check"),
               "final_net_worth_real": s["summary"].get("final_net_worth_real"), "min_cash": s["summary"].get("min_cash")}
              for s in rep["stress"]]
    starter = next(c for c in val["checks"] if c["id"] == "ubs_starter_kit")["evidence"]["scenarios"]

    kids = lambda nid: [nodes[c["node_id"]]["label"] for c in nodes[nid].get("children", [])]  # noqa: E731
    return {
        "engine_version": val["engine_version"],
        "validation": {"passed": val["passed"], "total": val["total"], "duration_ms": val["duration_ms"],
                       "checks": [{"id": c["id"], "passed": c["passed"], "detail": c["detail"]} for c in val["checks"]]},
        "starter_kit": [{k: s[k] for k in ("scenario", "closing_cash", "min_cash", "first_negative_month", "match")} for s in starter],
        "tree": {k: top[k] for k in ("0", "1", "2", "3")},
        "tree_size": len(nodes),
        "master_children": {k: master[k] for k in ("2.1", "2.2", "2.3")},
        "master_exploration": {
            "levers": [{"label": l["label"], "low": l["low_value"], "high": l["high_value"], "unit": l["unit"],
                        "nw_low": l["final_net_worth_low"], "nw_high": l["final_net_worth_high"],
                        "swing": l["swing_final_net_worth"], "shortfall_at_high": l["cash_shortfall_high"]}
                       for l in ex["levers"][:5]],
            "break_even_salary_vs": be(ex),
            "timing_delta_nw": {t["delay_months"]: t.get("delta_final_net_worth") for t in ex["timing"]},
            "reverse_stress": {"status": ex["reverse_stress"]["status"], "value": ex["reverse_stress"]["value"]},
        },
        "pillar_3a_node_1": {"monthly_amount": p3a.get("monthly_amount"), "annual_cap": p3a.get("annual_cap"),
                             "options": {o["option"]: {k: o.get(k) for k in ("final_net_worth", "final_liquid", "tax_saved_by_3a")}
                                         for o in p3a.get("options", [])}},
        "personal_condition": {
            "intervention": SCHOLARSHIP,
            "patch": {k: patched[k] for k in ("2", "2.1", "2.2", "2.3")},
            "break_even_salary_vs_after": be(ex_p),
            "new_branch": {k: branch[k] for k in ("2.1", "2.2", "2.3", "2.c1") if k in branch},
            "leaf_path": leaf_path, "leaf": leaf[leaf_path[-1]], "leaf_stress": stress,
            "report_personal": rep.get("personal"),
        },
        "lumi": {**{nid: lumi_line(top[nid], nodes[nid].get("description", ""), kids(nid)) for nid in ("0", "2")},
                 **{f"{nid} (with the condition)": lumi_line(leaf[nid], nodes[nid].get("description", ""), kids(nid))
                    for nid in ("2.2", "2.2.1")}},
        "seconds": round(time.perf_counter() - t0, 1),
    }


def axa_figures():
    def summary(run):
        return json.loads((BENCH / run / "summary.json").read_text(encoding="utf-8"))["summary"]
    s, old = summary(BENCH_RUN), summary(BENCH_REUSED)
    rows = {}
    for name in ("frugal", "ocr_llm", "vlm_cheap", "vlm_small", "vlm_large"):
        a = (s.get(name) or old[name])["all"]
        rows[name] = {"field_accuracy": a["field_accuracy"], "key_field_accuracy": a.get("key_field_accuracy"),
                      "usd_per_doc": a["usd_per_doc"], "usd_per_1000": round(a["usd_per_doc"] * 1000, 2),
                      "latency_p50_s": a.get("latency_p50_s"), "escalation_rate": a.get("escalation_rate")}
    alexia = []
    for line in (BENCH / BENCH_RUN / "per_doc.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if d["strategy"] == "frugal" and d["doc_id"].startswith("P00001"):
            alexia.append({"doc": d["doc_id"], "variant": d["variant"], "accuracy": d["accuracy"],
                           "escalated": d["escalated"], "usd": d["cost_usd"]})
    spend = sum(json.loads(l).get("cost_usd", 0) for l in (BENCH / "spend_log.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())
    f, big = rows["frugal"], rows["vlm_large"]
    return {"strategies": rows,
            "cost_ratio_vs_frontier": round(big["usd_per_doc"] / f["usd_per_doc"]),
            "accuracy_gap_points": round((big["field_accuracy"] - f["field_accuracy"]) * 100, 1),
            "images_to_cloud_share": f["escalation_rate"],
            "alexia_docs": alexia, "alexia_docs_usd": round(sum(d["usd"] for d in alexia), 6),
            "benchmark_spend_usd": round(spend, 2)}


def imc_figures():
    """Nora's exchange case, run exactly as the snippet in docs/impact/README.md does."""
    text = (ROOT / "docs/impact/README.md").read_text(encoding="utf-8")
    case = json.loads(text.split("```json\n", 1)[1].split("```", 1)[0])
    out = {}
    for node in case["decisions"]:
        r = core.simulate(case["profile"], node, case["assumptions"], case["weather"], n_paths=1000, seed=42, sensitivity=False)
        m = r["metrics"]
        out[node["node_id"]] = {"label": node["label"], "final_cash": m["final_cash"],
                                "first_negative_month_ui": None if m["first_negative_month"] is None else m["first_negative_month"] + 1}
    return out


def test_counts(run: bool):
    py = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    res = {}
    for suite in ("core/tests", "api/tests"):
        cmd = py + ([suite] if run else ["--collect-only", suite])
        try:
            p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900 if run else 120)
            tail = (p.stdout.strip().splitlines() or [""])[-1]
        except subprocess.TimeoutExpired:
            tail = "timed out"
        res[suite] = tail
    web = sorted((ROOT / "web/src").rglob("*.test.js"))
    if run:
        try:
            p = subprocess.run("npm test --silent", cwd=ROOT / "web", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, shell=True)
            res["web"] = " · ".join(l.strip("# ").strip() for l in (p.stdout or "").splitlines() if re.match(r"# (tests|pass|fail)\b", l)) or "no summary (run npm ci?)"
        except subprocess.TimeoutExpired:
            res["web"] = "timed out"
    else:
        res["web"] = f"{sum(len(re.findall(r'^\s*(?:test|it)\(', f.read_text(encoding='utf-8'), re.M)) for f in web)} test() calls in {len(web)} files"
    return res


def pct(x):
    return f"{x * 100:.1f}%"


def show_row(r):
    gap = f"gap {chf(r['funding_gap_chf'])} from month {r['funding_gap_from_month']}" if r["funding_gap_chf"] else "no funding gap"
    w = f"holds in {r['holds_in_weather']}/{r['weather_of']} stress" if r["weather_of"] else ""
    return (f"  {r['node_id']:<6} {r['label'][:42]:<42} | {r['plan_check_label']} | {gap} | real 10y NW {chf(r['final_net_worth_real'])}"
            f" | {w} | B: {r['headline_b']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tests", action="store_true", help="run the test suites (slow) instead of only counting tests")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to cp1252
    figs ={"engine": engine_figures(), "axa": axa_figures(), "imc": imc_figures(), "tests": test_counts(a.tests)}
    if a.json:
        print(json.dumps(figs, indent=1, ensure_ascii=False))
        return
    e, x, i = figs["engine"], figs["axa"], figs["imc"]
    print(f"# Pitch figures · {time.strftime('%a %d %b %H:%M')} · engine {e['engine_version']} · git {subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()}\n")
    v = e["validation"]
    print(f"## Validation: {v['passed']}/{v['total']} in {v['duration_ms'] / 1000:.1f} s")
    for c in v["checks"]:
        print(f"  {'PASS' if c['passed'] else 'FAIL'} {c['id']}: {c['detail']}")
    print("\n## UBS starter kit (closing cash / lowest cash / first negative month, 1-based)")
    for s in e["starter_kit"]:
        fn = "never" if s["first_negative_month"] is None else f"month {s['first_negative_month'] + 1}"
        print(f"  {s['scenario']:<16} {chf(s['closing_cash'])} / {chf(s['min_cash'])} / {fn} · match {s['match']}")
    print(f"\n## Tree ({e['tree_size']} nodes): root and level 1")
    for r in e["tree"].values():
        print(show_row(r))
    print("\n## Demo path: Do a master's (2) and its children")
    for r in e["master_children"].values():
        print(show_row(r))
    me = e["master_exploration"]
    print("  levers (10-year net worth across the sourced range):")
    for l in me["levers"]:
        print(f"    {l['label']}: {l['low']} → {l['high']} {l['unit']} moves it {chf(l['nw_low'])} → {chf(l['nw_high'])} (swing {chf(l['swing'])}); cash short even at high: {l['shortfall_at_high']}")
    print(f"  break-even salary after the master's vs node: {me['break_even_salary_vs']} (CHF/month, today's prices)")
    print(f"  timing, change in 10-year net worth if started later (months: CHF): {me['timing_delta_nw']}")
    print(f"  reverse stress: {me['reverse_stress']}")
    pc = e["personal_condition"]
    print(f"\n## Personal condition on node 2 (Make it mine): {pc['intervention']}")
    print("  mode 'Apply to this branch' (node_patches):")
    for r in pc["patch"].values():
        print(show_row(r))
    print(f"  break-even salary after the condition: {pc['break_even_salary_vs_after']}")
    print("  mode 'Add as a new branch' (custom_nodes):")
    for r in pc["new_branch"].values():
        print(show_row(r))
    print(f"  leaf {' → '.join(pc['leaf_path'])} with the condition:")
    print(show_row(pc["leaf"]))
    print("  leaf under stress: " + "; ".join(f"{s['weather']} {s['plan_check']} (real NW {chf(s['final_net_worth_real'])})" for s in pc["leaf_stress"]))
    print(f"  report shows personal conditions: {pc['report_personal']}")
    p3 = e["pillar_3a_node_1"]
    print(f"\n## Pillar 3a lever on Start working (1): CHF {p3['monthly_amount']}/month, cap CHF {p3['annual_cap']}/year")
    for k, o in p3["options"].items():
        print(f"  {k}: 10y net worth {chf(o['final_net_worth'])} · liquid {chf(o['final_liquid'])} · tax saved {chf(o['tax_saved_by_3a'])}")
    print("\n## Lumi's English bubbles (template, from engine fields)")
    for nid, line in e["lumi"].items():
        print(f"  [{nid}] {line}")
    print("\n## AXA benchmark (60 synthetic documents)")
    for k, s in x["strategies"].items():
        print(f"  {k:<10} field {pct(s['field_accuracy'])} · key {pct(s['key_field_accuracy'])} · USD {s['usd_per_doc']:.5f}/doc · USD {s['usd_per_1000']}/1,000 · p50 {s['latency_p50_s']} s")
    print(f"  frontier/frugal cost ratio: {x['cost_ratio_vs_frontier']}× · accuracy gap {x['accuracy_gap_points']} points · documents escalated to a cloud VLM: {pct(x['images_to_cloud_share'])}")
    print(f"  Alexia's 3 documents: {x['alexia_docs']} · total USD {x['alexia_docs_usd']}")
    print(f"  all benchmark experiments: USD {x['benchmark_spend_usd']}")
    print("\n## IMC: Nora's exchange case (docs/impact/README.md)")
    for nid, r in i.items():
        print(f"  {nid}: {r['label']}: final cash {r['final_cash']} · first negative month {r['first_negative_month_ui'] or 'none'}")
    print(f"\n## Tests ({'ran' if a.tests else 'collected; use --tests for pass counts'})")
    for k, t in figs["tests"].items():
        print(f"  {k}: {t}")
    print(f"\n(engine figures computed in {e['seconds']} s)")


if __name__ == "__main__":
    main()
