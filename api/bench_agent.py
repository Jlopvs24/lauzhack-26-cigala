"""Benchmark the explanatory agent across cheap models (AXA frugality evidence).

python -m api.bench_agent [model ...]      -> prints a table, writes api/bench_agent_results.json
Spends real money (≈ USD 0.001 per model for the default question set).
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

from api.env import load_env

load_env()

from api import agent  # noqa: E402

QUESTIONS = [
    ("¿Por qué el máster se queda sin dinero?", {"path": ["2"]}),
    ("What changes if I take the student loan instead?", {"path": ["2", "2.2"]}),
    ("Compare starting to work with moving abroad.", {"path": ["1"]}),
    ("Et si le salaire junior était de 3800 francs ?", {"path": ["1"]}),
    ("Which assumption matters most here?", {"path": ["3"]}),
    ("Should I do the master's? Just tell me what's best.", {"path": ["2"]}),  # must not recommend
]
MODELS = ["qwen/qwen3.7-flash", "mistralai/ministral-8b-2512", "openai/gpt-6-luna",
          "google/gemini-3.1-flash-lite", "anthropic/claude-haiku-5.5"]
ADVICE_WORDS = ["you should", "i recommend", "best option", "deberías", "te recomiendo", "tu devrais", "je recommande"]


def run(models: list[str]) -> list[dict]:
    rows = []
    for m in models:
        os.environ["AGENT_MODEL"] = m
        os.environ["AGENT_FALLBACK_MODELS"] = m
        for q, ctx in QUESTIONS:
            t0 = time.perf_counter()
            r = agent.ask(q, {"profile": json.loads((Path(__file__).parent / "fixtures/alexia.json").read_text()),
                              **ctx})
            rows.append({"model": m, "question": q, "mode": r["mode"], "grounded_llm": r["mode"] == "llm",
                         "advice": any(w in r["answer"].lower() for w in ADVICE_WORDS),
                         "lang": r["language"], "cost_usd": r["cost_usd"], "tokens": r["tokens"],
                         "latency_ms": int((time.perf_counter() - t0) * 1000),
                         "tools": [t["tool"] for t in r["tool_traces"]], "answer": r["answer"], "error": r["error"]})
            print(f"{m:32} {rows[-1]['latency_ms']:6d} ms ${r['cost_usd']:.6f} {r['mode']:8} {q[:40]}", flush=True)
    return rows


def summarize(rows: list[dict]) -> None:
    print(f"\n{'model':32} {'llm-ok':>6} {'advice':>6} {'p50 ms':>7} {'max ms':>7} {'USD/q':>9}")
    for m in dict.fromkeys(r["model"] for r in rows):
        rs = [r for r in rows if r["model"] == m]
        lat = [r["latency_ms"] for r in rs]
        print(f"{m:32} {sum(r['grounded_llm'] for r in rs):>3}/{len(rs)} {sum(r['advice'] for r in rs):>6} "
              f"{int(statistics.median(lat)):>7} {max(lat):>7} {statistics.mean(r['cost_usd'] for r in rs):>9.6f}")


if __name__ == "__main__":
    rows = run(sys.argv[1:] or MODELS)
    (Path(__file__).parent / "bench_agent_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                                                    encoding="utf-8")
    summarize(rows)
