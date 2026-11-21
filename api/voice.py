"""Server-side voice (optional). Provider decision is OPEN: see api/VOICE.md.

Default proposal: browser Web Speech API (free, no audio leaves the device for TTS).
These endpoints exist as the server fallback, using Together (organizers' key):
- STT: openai/whisper-large-v3 via /v1/audio/transcriptions
- TTS: cartesia/sonic via /v1/audio/speech
Each call is logged in USAGE with its estimated cost.
"""
from __future__ import annotations

import os
import time

import httpx

from api.llm import USAGE

TOGETHER = "https://api.together.xyz/v1"
STT_MODEL = os.environ.get("STT_MODEL", "openai/whisper-large-v3")
TTS_MODEL = os.environ.get("TTS_MODEL", "cartesia/sonic-2")
# Price assumptions for logging (USD); update from provider pages. Together lists whisper
# per audio minute and Cartesia per character.
STT_USD_PER_MIN = float(os.environ.get("STT_USD_PER_MIN", "0.0015"))
TTS_USD_PER_1K_CHARS = float(os.environ.get("TTS_USD_PER_1K_CHARS", "0.065"))

_TTS_VOICES = {"en": "friendly sidekick", "es": "friendly sidekick", "fr": "friendly sidekick",
               "de": "friendly sidekick"}


def _key() -> str | None:
    return os.environ.get("TOGETHER_API_KEY")


def status() -> dict:
    return {"server_voice": bool(_key()), "stt_model": STT_MODEL, "tts_model": TTS_MODEL,
            "recommended_client": "web-speech-api"}


def stt(audio: bytes, filename: str, language: str | None = None) -> dict:
    if not _key():
        return {"text": None, "error": "TOGETHER_API_KEY not set", "cost_usd": 0.0, "model": None}
    t0 = time.perf_counter()
    data = {"model": STT_MODEL, "response_format": "verbose_json"}
    if language:
        data["language"] = language[:2]
    r = httpx.post(f"{TOGETHER}/audio/transcriptions", data=data,
                   files={"file": (filename, audio)},
                   headers={"Authorization": f"Bearer {_key()}"}, timeout=60)
    latency = int((time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        return {"text": None, "error": f"together {r.status_code}: {r.text[:200]}", "cost_usd": 0.0,
                "model": STT_MODEL}
    j = r.json()
    dur = float(j.get("duration") or 0.0)
    cost = dur / 60 * STT_USD_PER_MIN
    USAGE.add({"ts": time.time(), "purpose": "stt", "model": STT_MODEL, "cost_usd": cost,
               "audio_seconds": dur, "latency_ms": latency})
    return {"text": (j.get("text") or "").strip(), "language": j.get("language"), "audio_seconds": dur,
            "cost_usd": round(cost, 6), "cost_is_estimate": True, "model": STT_MODEL, "provider_latency_ms": latency}


def tts(text: str, language: str | None = None, voice: str | None = None) -> tuple[bytes, dict]:
    if not _key():
        raise RuntimeError("TOGETHER_API_KEY not set")
    t0 = time.perf_counter()
    lang = (language or "en")[:2]
    body = {"model": TTS_MODEL, "input": text[:2000], "voice": voice or _TTS_VOICES.get(lang, "friendly sidekick"),
            "response_format": "mp3", "language": lang}
    r = httpx.post(f"{TOGETHER}/audio/speech", json=body,
                   headers={"Authorization": f"Bearer {_key()}"}, timeout=60)
    latency = int((time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        raise RuntimeError(f"together tts {r.status_code}: {r.text[:200]}")
    cost = len(text) / 1000 * TTS_USD_PER_1K_CHARS
    USAGE.add({"ts": time.time(), "purpose": "tts", "model": TTS_MODEL, "cost_usd": cost,
               "chars": len(text), "latency_ms": latency})
    return r.content, {"cost_usd": round(cost, 6), "model": TTS_MODEL, "media_type": "audio/mpeg",
                       "provider_latency_ms": latency}
