# api/ — cigala backend (thread 2)

FastAPI bridge between the engine (`core/`), multimodal input (`multimodal/`) and the web (`web/`).

```bash
pip install -r api/requirements.txt -r multimodal/requirements.txt
python -m api.fetch_models --fp32                 # local TTS model, once
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
| POST | `/tree/expand` | `{profile?, path, assumptions?, weather?, uncertainty?, exploration?, sensitivity?}` | visible tree (below). Lean by default (`exploration`/`sensitivity` false, ~50 ms); cached by request (`cached: true`) |
| POST | `/tree/explore` | `{profile?, path, assumptions?, weather?}` | current node only: `{node_id, exploration, sensitivity, plan_check, facts[]}` via `core.explore` (~0.2 s, cached) |
| POST | `/simulate` | `{profile?, node, assumptions?, weather?, uncertainty?}` | `{result: SimulationResult}` |
| POST | `/profiles/extract` | multipart `files[]` (PDF/JPG/PNG, audio also accepted), `text?`, `audio?`, `base_profile?` (JSON string) | `{profile (with per-field provenance), extractor, cost_usd, latency_ms, missing_fields, checks, documents, transcripts}` via `multimodal.extract`; mock (`extractor: "mock"`, `mock_reason`) only if multimodal deps are missing Sets `profile.income_basis = "net_before_tax"` (payslip net, income tax still charged) unless the extractor states one. |
| POST | `/agent/ask` | `{question, context}` | answer + traces (below) |
| POST | `/agent/ask/stream` | same as `/agent/ask` | Server-Sent Events: `start` at once, `sentence` (each checked before sending), `replace` (fallback text), `done` (same fields as `/agent/ask` + `first_sentence_ms`) |
| POST | `/report` | `{profile?, path, assumptions?, uncertainty?, language?}` | path report: 12 structured sections, numbers only from the engine; summary is the deterministic template (no LLM call, ~1 s cold, cached) |
| POST | `/report/summary` | same body | grounded LLM rewording/translation of the summary (frugal model, ~3-4 s, cached); falls back to the template if any number is not in it |
| POST | `/tree/personalize` | `{profile?, path, node_id?, text? or audio_b64?, language?, mode?}` | the user's own condition → a proposed patch or new branch (`proposal.apply` to send back as `node_patches` / `custom_nodes`), or one clarifying question; amounts must be in the user's words |
| POST | `/tree/compare` | `{profile?, paths (2-4), baseline?, ...}` | side-by-side options: metrics, series, impact of each option alone, per-metric orders (no LLM) |
| POST | `/tree/combine` | `{profile?, a, b, assumptions?, weather?}` | two decisions together (`core.combine`) |
| POST | `/tree/surface` | `{profile?, path, x, y, n?, compare_to?}` | 2-lever heatmap (`core.surface`); a lever may be an assumption id |
| POST | `/tree/smallest_change` | `{profile?, path, target?, levers?}` | what would fix this branch, per lever, plus `facts[]` |
| POST | `/tree/timing_scan` | `{profile?, path, delays?}` | the decision started later |

All engine routes (and `/agent/ask*` via `context`) accept optional `custom_nodes` and `node_patches`, forwarded to core (501 until core supports them).
| POST | `/voice/stt` | multipart `audio` (WAV/MP3), `language?` | `{text, language, cost_usd, model}` |
| POST | `/voice/ask` | multipart `audio`, `context` (JSON string), `language?` | `/agent/ask` response + `transcript`, `stt` |
| POST | `/voice/tts` | `{text, language?, voice?}` | `audio/wav` (local Kokoro, cost 0; headers `X-Model`, `X-Cost-USD`, `X-Audio-Seconds`), or 503 → use browser `speechSynthesis` |
| POST | `/voice/tts/stream` | same | NDJSON, one line per sentence `{index, text, audio_b64, audio_seconds, synth_ms}`, then `{done}` |
| GET | `/voice/fillers?language=en` | – | short phrases for call mode |
| GET | `/call` | – | realtime call prototype (`api/static/call.html`, client `api/static/call.js`) |
| GET | `/live/status` | – | Lumi Live availability `{available, reason (no_key / budget / busy), model, privacy}` |
| POST | `/live/token` | `{context, language?}` | starts a Live session: one-use token (60 s), `ws_path`, model, voice, config (system instruction, tools). See "Lumi Live" below |
| WS | `/live/ws?token=` | binary PCM16 16 kHz + JSON | realtime voice proxy to Gemini Live (protocol in `api/live.py`) |
| GET | `/usage` | – | cumulative LLM/voice calls, tokens and USD |
| GET | `/validation` | `?refresh=true` optional | live engine checks from `core.validation()`: `{engine_version, passed, total, all_passed, duration_ms, how, checks[{id, label, passed, detail, evidence, ms}], age_s, cached}`; cached 60 s (`VALIDATION_TTL_S`) |

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

## Exploration first (UBS feedback, issue #21)

Results are deterministic "if this, then that" paths. With `uncertainty: false` (the default), stochastic fields are
null or empty (`n_paths: 0`, empty band arrays). Use the deterministic fields: `metrics.final_net_worth`,
`metrics.min_cash`, `metrics.first_negative_month` and `goals[].met_deterministic`.

The agent speaks in if-then terms ("if you take X, then under these assumptions…"). A deterministic guard rewrites
forecast phrasing (`forecast_phrases_softened`). It mentions simulated-path spreads only when `context.uncertainty`
is true. Tools:
- `get_node`, `compare_nodes`
- `what_if` (pull one lever)
- `get_exploration`: the engine's levers, break-even, goal-seek, reverse stress and timing analyses, when present
- `what_would_have_to_be_true`: an engine-computed bisection for the threshold value of a lever at which cash
  never goes negative, the node catches up with a sibling, or a goal is reached

## Running it (shared server)

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

- Each worker warms core's tree in a background thread at start-up (~1 s), and again when `/profiles/extract`
  returns a new profile.
- Kokoro TTS runs in its own worker process per API worker (4 ONNX threads, `TTS_THREADS`), with audio cached
  per (text, language, voice). Engine requests never wait for TTS.
- Responses of `/tree/expand`, `/tree/explore` and `/report` are cached per worker (LRU of 256, `API_CACHE_ITEMS`).
- The streaming agent uses `AGENT_STREAM_MODEL` (default `anthropic/claude-haiku-5.5`, fastest first token measured:
  ~1.3 s), falling back to the normal chain.

## LLM budget guard

Every paid LLM call (agent, stream, report summary, personalize, server STT) checks today's spend, summed from
`api/usage.jsonl` across all workers. At `LLM_DAILY_BUDGET_USD` (default 2.0) calls are refused and every route
falls back to its template or clarifying question. Engine routes and local TTS are never affected. `GET /usage`
and `GET /health` show `budget` / `llm_budget` `{daily_limit_usd, spent_today_usd, remaining_usd, exceeded}`.
Stream model: `AGENT_STREAM_MODEL` (default Haiku 5.5, about 1.4 s to the first sentence and about USD 0.0008 per
answer; qwen measured 1.3–4.0 s, median 2.7 s, about USD 0.0001). Every other LLM path uses the frugal default chain.

## Models & privacy

| Step | Default | Where it runs | Fallback (only when the default fails) |
|---|---|---|---|
| Agent chat, streamed answers, report summary, personal-conditions parser | **`qwen/qwen3.6-35b-a3b`** (Qwen3.6-35B-A3B, **open weights, Apache-2.0**, `Qwen/Qwen3.6-35B-A3B` on Hugging Face; mixture of experts, about 3B active parameters) | OpenRouter today; **any OpenAI-compatible server** with `LLM_BASE_URL` (vLLM, Ollama, llama.cpp…), optional `LLM_API_KEY` | `qwen/qwen3.7-flash` (Qwen's API-only model, not open-weight), then `anthropic/claude-haiku-5.5` (proprietary) |
| Personal conditions, common phrasings | deterministic rules (`api/personalize_rules.py`) | API process, no model | the LLM row above |
| Text-to-speech | Kokoro-82M (Apache-2.0) | locally, in a worker process | browser `speechSynthesis` |
| Speech-to-text | browser `SpeechRecognition` | the user's browser | `google/gemini-3.1-flash-lite` via OpenRouter, for voice notes and Firefox only; it stays on OpenRouter even with `LLM_BASE_URL` |
| Documents (OCR) | RapidOCR / PDF text (thread 3, `multimodal/`) | locally | a small extraction LLM, then a vision model on failed checks (see `multimodal/README.md`) |

- **Open weights:** the Qwen model id we used before, `qwen/qwen3.7-flash`, is an API-only model with no published weights, so it is now only a fallback. The default is an Apache-2.0 open-weight Qwen. Running it on your own server keeps the conversation off third-party APIs. Set `LLM_BASE_URL=http://localhost:11434/v1` with `AGENT_MODEL=<the local model name>` and `AGENT_FALLBACK_MODELS=` (empty) so nothing leaves the machine. We do not run it locally for the demo.
- **Overrides:** `AGENT_MODEL`, `AGENT_FALLBACK_MODELS`, `AGENT_STREAM_MODEL` (defaults to `AGENT_MODEL`'s first model), `PERSONALIZE_FALLBACK_MODEL`. Every answer returns `model`, `primary_model` and `fallback_used`, and the server logs `agent answered_by=...`.
- **Latency, measured 21 Nov:** the first streamed sentence takes about 3–6 s with either Qwen model. Haiku measured about 1.4 s earlier; it is still one env var away (`AGENT_STREAM_MODEL=anthropic/claude-haiku-5.5`).
- **What the guards do:** financial figures come from the deterministic engine. The agent checks larger numeric claims (100 or more; years and small counts are skipped) against tool outputs or the user's own words, within 2% or CHF 1, and falls back to a template when a claim is not found. This is a number check, not a proof that every sentence is right. Advice and forecast wording are filtered, off-topic and injection text is refused before any LLM call, and spend is capped per day (`LLM_DAILY_BUDGET_USD`).

## Lumi Live (optional realtime voice, thread 11)

A spoken conversation with Lumi, Gemini-Live style: the user just talks, Lumi answers in under a second, can be
interrupted (barge-in), and every number still comes from our engine through tools.

**Privacy: Live is an OPTIONAL mode. While a Live call is open, the user's voice and this branch's engine results go
to Google (Gemini Live API).** The default mode stays private: open-weight Qwen (or your own `LLM_BASE_URL`), local
Kokoro voice and browser speech recognition. The web says so on the call card.

- **How:** the browser never sees the key. `POST /live/token` builds the system prompt (the agent's own rules: scope,
  numbers only from the engine, no recommendations, if-then wording, user's language EN/ES/FR/DE, plus the current
  node's results preloaded) and returns a one-use token; `WS /live/ws` proxies browser ⇄ Gemini. Tool calls run here,
  against the engine, with the user's context (profile, path, assumptions, weather, custom_nodes, node_patches).
  When the user moves in the tree, the web sends `{type: "context"}` and the proxy tells the model (no reply).
- **Tools:** `get_current_node`, `get_node`, `compare_nodes`, `what_if`, `what_would_fix_it` (core smallest_change),
  `what_would_have_to_be_true`, `get_exploration`, `get_assumptions`, `explain_assumption`. Personalisation is not
  exposed in Live (it needs a confirm step in the app).
- **Guards:** audio cannot be filtered before it is spoken, so the rules live in the prompt; after each turn the
  transcript is number-checked against tool outputs (`turn_complete.grounding`, logged when a number is not found).
  Budget: refused when `LLM_DAILY_BUDGET_USD` is reached, and a running call ends when it would pass it. One session
  per API process (`LIVE_MAX_SESSIONS`), ends after `LIVE_IDLE_S` (180) of silence or `LIVE_MAX_S` (600) in total.
  Each session is logged in `api/usage.jsonl` (`purpose: "live"`, tokens, estimated USD, turns, tool calls, first
  audio ms). Prices are estimates (`LIVE_PRICE_*`).
- **Config:** `GEMINI_API_KEY`, `LIVE_MODEL` (default `gemini-3.1-flash-live-preview`), `LIVE_VOICE` (default
  `Aoede`). No key ⇒ `/live/status` says `no_key` and the web keeps the classic call.
- **Model choice, measured 21 Nov:** `gemini-3.1-flash-live-preview` called the tool in 0.44 s and spoke after
  0.97 s. `gemini-2.5-flash-native-audio-latest` took 6.3 s and answered with an invented number instead of calling
  the tool.
- **Latency through our proxy:** setup 0.8 s; first audio 0.56–0.63 s after a turn with no tool call, about 1.3–2.8 s
  when an engine tool runs first (what_would_fix_it ≈ 1.8 s of engine time). A 30–60 s call costs about USD 0.01–0.02.
