"""Benchmark: field accuracy, USD cost and latency per document, per strategy.

    python -m multimodal.benchmark.run --strategies frugal vlm_small vlm_large --limit 12

Reads data/synthetic/manifest.jsonl (ground truth), writes
multimodal/benchmark/results/<run_id>/{per_doc.jsonl, summary.json, report.md}.
Costs are the USD amounts reported by OpenRouter for each call.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..extract import llm
from ..extract.documents import MODELS, extract_document
from ..extract.validate import strip_accents

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "synthetic"
RESULTS = ROOT / "multimodal" / "benchmark" / "results"
PROFILE_KEYS = {"payslip": ["net_monthly_income"], "bank_statement": ["closing_balance", "income_credit", "rent_debit"],
                "rental_contract": ["monthly_rent_total"]}


def same(truth, pred) -> bool:
    if truth is None:
        return pred is None
    if pred is None:
        return False
    if isinstance(truth, (int, float)):
        try:
            return abs(float(pred) - float(truth)) <= 0.011
        except (TypeError, ValueError):
            return False
    norm = lambda s: re.sub(r"[^a-z0-9]", "", strip_accents(str(s)))
    return norm(truth) == norm(pred)


def score(doc, res) -> dict:
    truth = doc["truth"]
    per = {k: same(v, res.fields.get(k)) if res.doc_type == doc["doc_type"] else False for k, v in truth.items()}
    keys = PROFILE_KEYS[doc["doc_type"]]
    return {"fields": per, "accuracy": sum(per.values()) / len(per),
            "key_accuracy": sum(per[k] for k in keys) / len(keys), "type_ok": res.doc_type == doc["doc_type"]}


def run_one(doc, strategy, run_id):
    try:
        res = extract_document(DATA / doc["file"], strategy, tag=f"bench:{run_id}")
        sc = score(doc, res)
        out = res.to_dict()
        err = None
    except Exception as e:  # keep the run going; count as a miss
        sc = {"fields": {k: False for k in doc["truth"]}, "accuracy": 0.0, "key_accuracy": 0.0, "type_ok": False}
        out, err = {"cost_usd": 0.0, "seconds": 0.0, "escalated": False}, repr(e)[:300]
    return {"doc_id": doc["doc_id"], "doc_type": doc["doc_type"], "variant": doc["variant"], "lang": doc["lang"],
            "strategy": strategy, **sc, "cost_usd": out["cost_usd"], "seconds": out["seconds"],
            "escalated": out.get("escalated", False), "pred": out.get("fields"),
            "confidence": out.get("confidence"), "error": err}


def summarise(rows):
    def agg(rs):
        return {"n": len(rs), "field_accuracy": round(statistics.mean(r["accuracy"] for r in rs), 4),
                "key_field_accuracy": round(statistics.mean(r["key_accuracy"] for r in rs), 4),
                "doc_type_accuracy": round(statistics.mean(r["type_ok"] for r in rs), 4),
                "usd_per_doc": statistics.mean(r["cost_usd"] for r in rs),
                "usd_total": sum(r["cost_usd"] for r in rs),
                "latency_p50_s": round(statistics.median(r["seconds"] for r in rs), 2),
                "latency_mean_s": round(statistics.mean(r["seconds"] for r in rs), 2),
                "escalation_rate": round(statistics.mean(bool(r["escalated"]) for r in rs), 3),
                "errors": sum(bool(r["error"]) for r in rs)}
    out = {}
    by = defaultdict(list)
    for r in rows:
        by[r["strategy"]].append(r)
    for s, rs in by.items():
        out[s] = {"all": agg(rs)}
        for dim in ("variant", "doc_type", "lang"):
            g = defaultdict(list)
            for r in rs:
                g[r[dim]].append(r)
            out[s][dim] = {k: agg(v) for k, v in sorted(g.items())}
    return out


def report(summary, meta) -> str:
    L = [f"# Extraction benchmark ({meta['run_id']})", "",
         f"{meta['n_docs']} synthetic Swiss documents (payslips, bank statements, rental contracts; FR/DE/IT/EN; "
         "clean PDF, scanned, phone photo, low-res) with known ground truth.", "",
         "| Strategy | Models | Field accuracy | Key-field accuracy | USD / doc | USD per 1,000 docs | Latency p50 (s) | Escalated |",
         "|---|---|---|---|---|---|---|---|"]
    for s, d in summary.items():
        a = d["all"]
        L.append(f"| {s} | {meta['models'][s]} | {a['field_accuracy']:.1%} | {a['key_field_accuracy']:.1%} | "
                 f"{a['usd_per_doc']:.6f} | {a['usd_per_doc'] * 1000:.2f} | {a['latency_p50_s']} | {a['escalation_rate']:.0%} |")
    for dim in ("variant", "doc_type", "lang"):
        L += ["", f"## Field accuracy by {dim}", "", "| Strategy | " + " | ".join(next(iter(summary.values()))[dim]) + " |",
              "|---|" + "---|" * len(next(iter(summary.values()))[dim])]
        for s, d in summary.items():
            L.append(f"| {s} | " + " | ".join(f"{v['field_accuracy']:.1%}" for v in d[dim].values()) + " |")
    L += ["", "Key fields = the ones that feed the Profile (net income, rent, cash). Costs as reported by OpenRouter.",
          "Latency includes local OCR on a laptop CPU for the frugal strategies."]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", nargs="+", default=["frugal", "vlm_small", "vlm_large"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4, help="parallel API calls for VLM strategies")
    ap.add_argument("--budget", type=float, default=3.0, help="abort if total logged spend exceeds this (USD)")
    ap.add_argument("--reuse", default="", help="run_id whose rows are reused for strategies not re-run here")
    args = ap.parse_args()

    docs = [json.loads(l) for l in open(DATA / "manifest.jsonl", encoding="utf-8")]
    if args.limit:
        docs = docs[:args.limit]
    run_id = time.strftime("%Y%m%d-%H%M%S")
    out = RESULTS / run_id
    out.mkdir(parents=True, exist_ok=True)
    spent0 = llm.total_spend()
    rows = []
    for s in args.strategies:
        if llm.total_spend() > args.budget:
            print(f"budget {args.budget} USD reached, skipping {s}")
            continue
        if s.startswith("vlm"):
            with ThreadPoolExecutor(args.workers) as ex:
                rows += list(ex.map(lambda d: run_one(d, s, run_id), docs))
        else:  # sequential: honest per-document latency for local OCR
            rows += [run_one(d, s, run_id) for d in docs]
        done = [r for r in rows if r["strategy"] == s]
        print(f"{s}: acc={statistics.mean(r['accuracy'] for r in done):.3f} "
              f"cost={sum(r['cost_usd'] for r in done):.4f} USD")
    reused = []
    if args.reuse:
        ids = {d["doc_id"] for d in docs}
        for l in open(RESULTS / args.reuse / "per_doc.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if r["strategy"] not in args.strategies and r["doc_id"] in ids:
                rows.append(r)
                reused.append(r["strategy"])
    with open(out / "per_doc.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = summarise(rows)
    meta = {"run_id": run_id, "n_docs": len(docs), "strategies": args.strategies,
            "models": {"frugal": f"local OCR + {MODELS['text_small']} (+{MODELS['escalation_vlm']} on failed checks / unreadable captures)",
                       "ocr_llm": f"local OCR + {MODELS['text_small']}",
                       "vlm_small": MODELS["vlm_small"], "vlm_cheap": MODELS["vlm_cheap"], "vlm_large": MODELS["vlm_large"]},
            "spend_this_run_usd": round(llm.total_spend() - spent0, 6),
            "reused_from": {s: args.reuse for s in sorted(set(reused))}}
    (out / "summary.json").write_text(json.dumps({"meta": meta, "summary": summary}, indent=2), encoding="utf-8")
    (out / "report.md").write_text(report(summary, meta), encoding="utf-8")
    print(report(summary, meta))
    print(f"spend this run: {meta['spend_this_run_usd']} USD -> {out}")


if __name__ == "__main__":
    main()
