# api/ — cigala backend (thread 2)

FastAPI bridge between the engine (`core/`), multimodal input (`multimodal/`) and the web (`web/`).

```bash
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8000      # from the repo root
# docs: http://localhost:8000/docs
python -m pytest api/tests -q
```

Keys are read from `.env.local` at the repo root (`OPENROUTER_API_KEY`, `TOGETHER_API_KEY`). Without them the agent answers with templates and server voice is off; everything else works.

**Engine status:** until `core/` exposes `expand()` and `simulate()`, the API uses `api/mock_engine.py` (same JSON shapes, `"engine": "mock"` in every result). Its numbers are computed, not hard-coded, from the UBS kit's illustrative Alexia assumptions.

## Every response

`cost_usd`, `latency_ms`, `model` at the top level (engine calls: `cost 0`, `model "engine:mock"`). `GET /usage` = cumulative LLM/voice spend since start.

## Routes

| Method | Route | Body | Returns |
|---|---|---|---|
| GET | `/health` | – | engine, llm, voice status |
| GET | `/profiles/demo` | – | `{profile}` (Alexia) |
| GET | `/assumptions` | – | `{assumptions: [Assumption]}` |
| POST | `/tree/expand` | `{profile?, path, assumptions?, weather?}` | visible tree (below) |
| POST | `/simulate` | `{profile?, node, assumptions?, weather?}` | `{result: SimulationResult}` |
| POST | `/profiles/extract` | multipart `files[]`, `text` | `{profile, extractor}` (mock until thread 3) |
| POST | `/agent/ask` | `{question, context}` | answer + traces (below) |
| POST | `/voice/stt` | multipart `audio` (WAV/MP3), `language?` | `{text, language, cost_usd, model}` |
| POST | `/voice/ask` | multipart `audio`, `context` (JSON string), `language?` | `/agent/ask` response + `transcript`, `stt` |
| POST | `/voice/tts` | `{text, language?, voice?}` | `audio/wav` (local Kokoro, cost 0; headers `X-Model`, `X-Cost-USD`, `X-Audio-Seconds`), or 503 → use browser `speechSynthesis` |
| POST | `/voice/tts/stream` | same | NDJSON, one line per sentence `{index, text, audio_b64, audio_seconds, synth_ms}`, then `{done}` |
| GET | `/voice/fillers?language=en` | – | short phrases for call mode |
| GET | `/call` | – | realtime call prototype (`api/static/call.html`, client `api/static/call.js`) |
| GET | `/usage` | – | cumulative LLM/voice calls, tokens and USD |

Voice: TTS = local Kokoro-82M (`python -m api.fetch_models --fp32` once), browser `speechSynthesis` as fallback. STT = browser `SpeechRecognition`, OpenRouter as fallback. Call mode = browser STT → `/agent/ask` with `context.mode: "call"` (max 2 sentences) → `/voice/tts/stream`, with barge-in. Measurements and rejected options: `api/VOICE.md`.

`profile` omitted ⇒ Alexia. `assumptions` = overrides `[{"id": "AS-salary-junior-ch", "value": 4500}]`. `weather` ⊂ `recession | inflation | market_crash | job_loss`.

### `/tree/expand`

`path` = chosen node ids from the root, as a chain: `[]`, `["2"]`, `["2", "2.2"]`. Going back one level = drop the last id.

```json
{
  "current": "2",
  "path": ["0", "2"],
  "nodes": [
    {"node_id": "0",   "parent_id": null, "label": "Today",                     "status": "chosen",  "depth": 0, "interventions": [], "assumptions_ref": [], "result": {"...": "SimulationResult"}},
    {"node_id": "2",   "parent_id": "0",  "label": "Master's degree (2 years)", "status": "chosen",  "depth": 1, "result": {}},
    {"node_id": "1",   "parent_id": "0",  "label": "Start working now",         "status": "sibling", "depth": 1, "result": {}},
    {"node_id": "2.1", "parent_id": "2",  "label": "Work part-time during the master's", "status": "child", "depth": 2, "result": {}}
  ],
  "assumptions": [{"id": "AS-market-return", "value": 0.05, "unit": "1/year", "source": "...", "editable": true}],
  "weather_options": {"recession": "...", "inflation": "...", "market_crash": "...", "job_loss": "..."},
  "engine": "mock", "cost_usd": 0, "latency_ms": 380, "model": "engine:mock"
}
```

Visible = root + chosen path (`chosen`) + siblings of the current node (`sibling`, show greyed) + its children (`child`). Siblings of earlier levels are pruned (not returned).

`result` follows `docs/contracts.md` SimulationResult: `deterministic.cash/net_worth` and `bands.net_worth.p10/p50/p90` have 121 points (month 0 = opening … month 120). `metrics.first_negative_month` is 0-indexed (6 ⇒ "month 7").

### `/agent/ask`

```json
{"question": "Why does the master's run out of money?",
 "context": {"path": ["2"], "node_id": "2", "language": "en", "weather": [], "assumptions": [],
             "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}}
```

```json
{"answer": "...", "language": "en", "mode": "llm | template",
 "grounding": {"grounded": true, "ungrounded_numbers": []},
 "tool_traces": [{"tool": "get_node", "args": {"node_id": "2"}, "trace_id": "sim-...", "node_id": "2"}],
 "cited_nodes": ["2"], "cost_usd": 0.00012, "tokens": {"prompt": 900, "completion": 80},
 "model": "qwen/qwen3.7-flash", "latency_ms": 1800, "error": null}
```

The character never computes: numbers come from engine tools (`get_node`, `compare_nodes`, `what_if`, `get_assumptions`). Every number in the answer is checked against tool outputs; if one is not found, or the LLM fails, the answer falls back to a template built from engine results (`mode: "template"`). `language` defaults to English, and the answer switches only when the question is clearly in es/fr/de (or `context.language` is set). The current node, its siblings and its children are preloaded from the engine, so most questions need one LLM call (~USD 0.0001, ~3–5 s with `qwen/qwen3.7-flash`). Model benchmark: `python -m api.bench_agent` (results in `api/bench_agent_results.json`).
