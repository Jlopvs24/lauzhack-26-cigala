"""Server-side voice. The provider decision is OPEN; findings and the proposal are in api/VOICE.md.

TTS (decided 14:15: the character reads its bubble aloud): local Kokoro-82M first
(api/tts_local.py), Together Cartesia if a working key exists, else 503 and the browser
speechSynthesis takes over. STT: browser first, server fallback:
- STT: OpenRouter chat model with audio input (default google/gemini-3.1-flash-lite), for
  browsers without SpeechRecognition (Firefox) and for recorded voice notes.
- TTS: Together /audio/speech when a working TOGETHER_API_KEY exists. OpenRouter's audio-output
  model (gpt-audio-mini) is NOT used: in our test it answered instead of reading the text verbatim,
  which could put numbers in the character's mouth that the engine never produced.
Every call is logged in USAGE with its cost (OpenRouter reports it; Together cost is estimated).
"""
from __future__ import annotations

import base64
import os
import time

import httpx

from api import llm
from api.llm import USAGE

STT_PROVIDER = os.environ.get("STT_PROVIDER", "openrouter")  # openrouter | together
STT_MODEL = os.environ.get("STT_MODEL", "google/gemini-3.1-flash-lite")
TOGETHER = "https://api.together.xyz/v1"
TOGETHER_STT_MODEL = "openai/whisper-large-v3"
TTS_MODEL = os.environ.get("TTS_MODEL", "cartesia/sonic-2")
STT_USD_PER_MIN = float(os.environ.get("STT_USD_PER_MIN", "0.0015"))  # Together whisper, estimate
TTS_USD_PER_1K_CHARS = float(os.environ.get("TTS_USD_PER_1K_CHARS", "0.065"))  # Cartesia, estimate

_FORMATS = {"wav": "wav", "mp3": "mp3", "mpeg": "mp3", "ogg": "ogg", "oga": "ogg", "webm": "ogg",
            "flac": "flac", "m4a": "m4a", "aac": "aac", "aiff": "aiff"}
STT_PROMPT = ("Transcribe this audio verbatim in the language spoken. Output only the transcript, "
              "then on the last line 'LANG: <ISO 639-1 code>'.")


class VoiceError(RuntimeError):
    pass


def tts_provider() -> str | None:
    want = os.environ.get("TTS_PROVIDER", "auto")
    if want in ("auto", "kokoro"):
        from api import tts_local
        if tts_local.available():
            return "kokoro"
    if want in ("auto", "together") and os.environ.get("TOGETHER_API_KEY"):
        return "together"
    return None


def status() -> dict:
    from api import tts_local
    return {"recommended_client": "web-speech-api", "tts_provider": tts_provider(), "kokoro": tts_local.status(),
            "server_stt": STT_PROVIDER if (llm.available() if STT_PROVIDER == "openrouter"
                                           else bool(os.environ.get("TOGETHER_API_KEY"))) else None,
            "stt_model": STT_MODEL if STT_PROVIDER == "openrouter" else TOGETHER_STT_MODEL,
            "server_tts": tts_provider() is not None}


def _fmt(filename: str, content_type: str | None) -> str:
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if ext in _FORMATS:
        return _FORMATS[ext]
    sub = (content_type or "").split("/")[-1].split(";")[0].lower()
    return _FORMATS.get(sub, "wav")


def stt(audio: bytes, filename: str, language: str | None = None, content_type: str | None = None) -> dict:
    if STT_PROVIDER == "together":
        return _stt_together(audio, filename, language)
    if not llm.available():
        raise VoiceError("OPENROUTER_API_KEY not set")
    prompt = STT_PROMPT + (f" Expected language: {language}." if language else "")
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "input_audio", "input_audio": {"data": base64.b64encode(audio).decode(), "format": _fmt(filename, content_type)}},
    ]}]
    r = llm.chat(msgs, model=STT_MODEL, purpose="stt", max_tokens=400, temperature=0)
    text = (r["message"].get("content") or "").strip()
    lang = language
    lines = text.splitlines()
    if lines and lines[-1].upper().startswith("LANG:"):
        lang = lines[-1].split(":", 1)[1].strip().lower()[:2] or lang
        text = "\n".join(lines[:-1]).strip()
    return {"text": text, "language": lang, "cost_usd": round(r["cost_usd"], 6), "cost_is_estimate": False,
            "model": r["model"], "provider_latency_ms": r["latency_ms"], "audio_bytes": len(audio)}


def _stt_together(audio: bytes, filename: str, language: str | None) -> dict:
    key = os.environ.get("TOGETHER_API_KEY")
    if not key:
        raise VoiceError("TOGETHER_API_KEY not set")
    t0 = time.perf_counter()
    data = {"model": TOGETHER_STT_MODEL, "response_format": "verbose_json"}
    if language:
        data["language"] = language[:2]
    r = httpx.post(f"{TOGETHER}/audio/transcriptions", data=data, files={"file": (filename, audio)},
                   headers={"Authorization": f"Bearer {key}"}, timeout=60)
    latency = int((time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        raise VoiceError(f"together stt {r.status_code}: {r.text[:200]}")
    j = r.json()
    dur = float(j.get("duration") or 0.0)
    cost = dur / 60 * STT_USD_PER_MIN
    USAGE.add({"ts": time.time(), "purpose": "stt", "model": TOGETHER_STT_MODEL, "cost_usd": cost,
               "audio_seconds": dur, "latency_ms": latency})
    return {"text": (j.get("text") or "").strip(), "language": j.get("language"), "audio_seconds": dur,
            "cost_usd": round(cost, 6), "cost_is_estimate": True, "model": TOGETHER_STT_MODEL,
            "provider_latency_ms": latency}


def tts(text: str, language: str | None = None, voice: str | None = None) -> tuple[bytes, dict]:
    """Whole text -> one audio file. Returns (bytes, meta)."""
    prov = tts_provider()
    if prov == "kokoro":
        from api import tts_local
        t0 = time.perf_counter()
        try:
            samples, sr = tts_local.synth_cached(text[:2000], language, voice)
        except Exception as e:  # noqa: BLE001
            raise VoiceError(f"kokoro failed: {e}") from e
        latency = int((time.perf_counter() - t0) * 1000)
        USAGE.add({"ts": time.time(), "purpose": "tts", "model": tts_local.model_name(), "cost_usd": 0.0,
                   "chars": len(text), "latency_ms": latency, "audio_seconds": round(len(samples) / sr, 2)})
        return tts_local.to_wav(samples, sr), {"cost_usd": 0.0, "model": tts_local.model_name(),
                                                "media_type": "audio/wav", "provider_latency_ms": latency,
                                                "audio_seconds": round(len(samples) / sr, 2)}
    if prov is None:
        raise VoiceError("server TTS unavailable: use the browser speechSynthesis (see api/VOICE.md)")
    key = os.environ["TOGETHER_API_KEY"]
    t0 = time.perf_counter()
    lang = (language or "en")[:2]
    body = {"model": TTS_MODEL, "input": text[:2000], "voice": voice or "friendly sidekick",
            "response_format": "mp3", "language": lang}
    r = httpx.post(f"{TOGETHER}/audio/speech", json=body, headers={"Authorization": f"Bearer {key}"}, timeout=60)
    latency = int((time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        raise VoiceError(f"together tts {r.status_code}: {r.text[:200]}")
    cost = len(text) / 1000 * TTS_USD_PER_1K_CHARS
    USAGE.add({"ts": time.time(), "purpose": "tts", "model": TTS_MODEL, "cost_usd": cost,
               "chars": len(text), "latency_ms": latency})
    return r.content, {"cost_usd": round(cost, 6), "model": TTS_MODEL, "media_type": "audio/mpeg",
                       "provider_latency_ms": latency}
