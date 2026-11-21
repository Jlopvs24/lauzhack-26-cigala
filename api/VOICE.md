# Voice: what we use and why (measured 2026-11-21)

Decided (plan.md, 14:15): the character reads its bubble aloud; the user can type, send a voice note, or **call** it.
Hardware for all numbers below: the team laptop (16 threads, CPU only, other agents running), English unless noted.

## Text-to-speech (character → audio)

| Option | Latency | Cost | Verbatim? | Verdict |
|---|---|---|---|---|
| **Kokoro-82M, local ONNX (fp32)** | first sentence 0.7–1.6 s; ~0.3 s of compute per s of audio | **0** | yes (TTS model, cannot add words) | **Implemented, default** in `/voice/tts` and `/voice/tts/stream` |
| Kokoro-82M int8 | ~2× slower than fp32 on this CPU | 0 | yes | fallback if disk is tight (88 MB vs 310 MB) |
| Browser `speechSynthesis` | instant | 0 | yes | fallback when the server has no TTS (503) |
| OpenRouter `openai/gpt-audio-mini` | first audio 1.9 s, but… | USD 0.0009–0.039 | **no** | **Rejected.** Plain prompt: it answered instead of reading. Strict "TTS engine" prompt: right words, then looped for 816 s of audio (148 s, USD 0.039). A chat model as TTS can put numbers in the character's mouth that the engine never produced. |
| Together `cartesia/sonic-2` | not measured | ~USD 0.065 / 1k chars | yes | key returns 401; code path kept (`TTS_PROVIDER=together`) |

Kokoro: Apache-2.0, 82M parameters, voices for en/es/fr/it/pt (`af_heart` default for English). Round-trip check (Kokoro → our STT): the English and French text came back word for word; Spanish dropped the minus sign, fixed by `speakable()` (`CHF -18'550` → "menos CHF 18550"). Numbers are never changed, only their spelling for speech.

Setup: `pip install -r api/requirements.txt && python -m api.fetch_models --fp32` (models go to `api/models/`, gitignored). On Windows paths with non-ASCII characters, espeak-ng data is copied once to `%TEMP%/cigala-espeak` automatically.

## Speech-to-text (user → text)

| Option | Latency | Cost | Verdict |
|---|---|---|---|
| **Browser `SpeechRecognition`** | live, interim results | 0 | default for chat dictation and call mode (Chrome, Edge, Safari) |
| OpenRouter `google/gemini-3.1-flash-lite` (audio in) | 2.8–3.5 s per clip | ~USD 0.0001 | server fallback: `/voice/stt`, `/voice/ask` (voice notes, Firefox) |
| OpenRouter `mistralai/voxtral-small-24b-2507` | 3.9 s | USD 0.00045 | 5× the cost |
| OpenRouter `qwen/qwen3.8-omni-flash` | 8.9 s | USD 0.00005 | too slow |

## Call mode (realtime, interruptible)

**Researched:**
- Speech-to-speech realtime APIs (OpenAI Realtime, Gemini Live): none is available with our keys. OpenRouter has no realtime/WebSocket endpoint, and the Together key is invalid.
- More importantly, a speech-to-speech model generates and speaks its own numbers. Nothing can check them before the user hears them, which breaks our core promise.

**Chosen: a cascaded pipeline where every sentence is checked before it is spoken.**

```
mic ──SpeechRecognition (browser, live)──► final utterance
                                          │  filler plays at once ("Let me check.", cached Kokoro)
                                          ▼
                         POST /agent/ask  {context.mode: "call"}
                         engine preload → cheap LLM → grounding check → advice guard → max 2 sentences
                                          ▼
                         POST /voice/tts/stream  (NDJSON, one WAV per sentence, first chunk ≤ 90 chars)
                                          ▼
                         Web Audio queue, gapless playback, bubble shows the sentence being spoken
barge-in: recognition keeps running while the character speaks; ≥ 2 words that are not an echo of the
current sentence → stop audio, abort requests, the user's words become the next turn.
```

Measured, 4 turns on node 2 (server side, excluding the browser): time to first answer audio was **2.3–4.4 s** in English (agent 1.4–2.8 s + first chunk 0.7–1.6 s), plus a 0.3 s filler right away. One Spanish turn took 10.6 s (the agent called a tool). Cost per turn is about USD 0.00005–0.00013 (LLM only; STT and TTS are free).

Grounding in call mode is the same as in chat: numbers are checked against engine tool outputs, sentences that recommend are dropped (`advice_removed`), and the template is the fallback. Known limit: the check verifies numbers, not every qualitative claim.

Prototype: `uvicorn api.main:app --port 8000`, open `http://localhost:8000/call` in Chrome or Edge. Reusable client: `api/static/call.js` (`CharacterCall`, no framework) for `web/`.
