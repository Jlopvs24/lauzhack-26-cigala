# Voice: options, measurements, proposal (decision OPEN, owner: lead)

Measured on 2026-11-21 from the API server (Windows, Lausanne Wi-Fi). Test clip: a 4.4 s English question in WAV.

## Speech-to-text (user → text)

| Option | Latency | Cost | Notes |
|---|---|---|---|
| **Browser Web Speech API** (`SpeechRecognition`) | live, partial results while speaking | 0 | Chrome/Edge/Safari. Not in Firefox. Chrome sends audio to Google's service; no key and nothing reaches our backend. |
| OpenRouter `google/gemini-3.1-flash-lite` (audio input) | 2.8–3.5 s | USD 0.00009–0.0001 per clip | Exact transcript. Returns the language. **Implemented** in `/voice/stt` and `/voice/ask`. |
| OpenRouter `mistralai/voxtral-small-24b-2507` | 3.9 s | USD 0.00045 | Exact, but 5× the cost of gemini-flash-lite. |
| OpenRouter `qwen/qwen3.8-omni-flash` | 8.9 s | USD 0.00005 | Exact, too slow. |
| Together `openai/whisper-large-v3` | not measured | ~USD 0.0015/min (list price) | The `TOGETHER_API_KEY` we got returns **401 invalid key**. Code path exists (`STT_PROVIDER=together`). |

## Text-to-speech (character → audio)

| Option | Latency | Cost | Notes |
|---|---|---|---|
| **Browser `speechSynthesis`** | immediate | 0 | Every browser. Reads the text verbatim, offline. Voice quality depends on the OS. Pick a voice per `language`. |
| OpenRouter `openai/gpt-audio-mini` (audio output) | first audio 2.4 s, full 32 s | USD 0.0009 for one sentence | **Rejected**: asked to read "The master's path runs short of cash in month 7", it improvised its own 15 s answer instead of reading it. A TTS that rewrites the text could say numbers the engine never produced. It also needs streaming. |
| Together `cartesia/sonic-2` | not measured (key 401) | ~USD 0.065 / 1k chars (list price) | Good voices, verbatim. Wired in `/voice/tts` if a working key appears. |

## Proposal

1. **Default: everything in the browser.** `SpeechRecognition` for input, `speechSynthesis` for output. Zero cost, the lowest latency, and no audio reaches our server. Good for AXA (frugal, private) and IMC (works for a student on a free deployment).
2. **Server fallback for STT only:** `POST /voice/ask` (audio → transcript → agent answer in one call, ~USD 0.0003 and ~7–8 s total) for Firefox and recorded voice notes. The web should record **WAV** (or MP3) because `webm/opus` is not a documented OpenRouter input format.
3. No server TTS unless we get a working Together key (then Cartesia for a nicer character voice in the demo).

Per voice turn, cost is about USD 0.0001 (agent only, browser voice) or about USD 0.0003 with server STT.
