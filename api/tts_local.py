"""Local text-to-speech with Kokoro-82M (Apache-2.0, ONNX, CPU).

Why: natural voice, reads the text verbatim (it is a TTS model, not a chat model, so it
cannot add numbers), costs 0 per call and no text or audio leaves our server.
Model files (~120 MB) are fetched with `python -m api.fetch_models` into api/models/ (gitignored).
"""
from __future__ import annotations

import io
import logging
import os
import re
import shutil
import tempfile
import threading
import wave
from pathlib import Path

import numpy as np

log = logging.getLogger("api.tts_local")

MODELS = Path(__file__).parent / "models"
VOICES_FILE = MODELS / "voices-v1.0.bin"
MODEL_FILES = ["kokoro-v1.0.onnx", "kokoro-v1.0.int8.onnx"]  # first one found wins (fp32 is faster on x86)

# language -> (kokoro lang code, default voice)
LANGS = {
    "en": ("en-us", "af_heart"),
    "es": ("es", "ef_dora"),
    "fr": ("fr-fr", "ff_siwis"),
    "it": ("it", "if_sara"),
    "pt": ("pt-br", "pf_dora"),
}
DEFAULT_VOICE_EN = os.environ.get("TTS_VOICE", "af_heart")

_lock = threading.Lock()
_kokoro = None
_model_name = None
_error: str | None = None


def model_path() -> Path | None:
    override = os.environ.get("KOKORO_MODEL")
    if override:
        return Path(override)
    for name in MODEL_FILES:
        if (MODELS / name).exists():
            return MODELS / name
    return None


def _ascii_espeak_dir() -> tuple[str, str] | None:
    """espeak-ng cannot open data under a non-ASCII path (e.g. C:\\Users\\Juan López).
    Copy its data to an ASCII-only directory once, if needed."""
    import espeakng_loader

    data, lib = espeakng_loader.get_data_path(), espeakng_loader.get_library_path()
    if str(data).isascii():
        return None
    for base in (os.environ.get("KOKORO_ESPEAK_DIR"), tempfile.gettempdir(), "C:/kokoro-espeak", "/tmp/kokoro-espeak"):
        if not base or not str(base).isascii():
            continue
        dst = Path(base) / "cigala-espeak"
        try:
            if not (dst / "espeak-ng-data" / "phontab").exists():
                shutil.copytree(data, dst / "espeak-ng-data", dirs_exist_ok=True)
            if not (dst / Path(lib).name).exists():
                shutil.copy(lib, dst / Path(lib).name)
            return str(dst / Path(lib).name), str(dst / "espeak-ng-data")
        except OSError:
            continue
    return None


def _load():
    global _kokoro, _model_name, _error
    if _kokoro is not None or _error is not None:
        return _kokoro
    mp = model_path()
    if mp is None or not VOICES_FILE.exists():
        _error = "kokoro model files missing (run: python -m api.fetch_models)"
        return None
    try:
        from kokoro_onnx import Kokoro
        from kokoro_onnx.config import EspeakConfig

        esp = _ascii_espeak_dir()
        cfg = EspeakConfig(lib_path=esp[0], data_path=esp[1]) if esp else None
        _kokoro = Kokoro(str(mp), str(VOICES_FILE), espeak_config=cfg)
        _model_name = "kokoro-82m" + ("-int8" if "int8" in mp.name else "")
        log.info("kokoro loaded: %s", mp.name)
    except Exception as e:  # noqa: BLE001
        _error = f"kokoro unavailable: {type(e).__name__}: {e}"
        log.warning(_error)
    return _kokoro


def available() -> bool:
    return _load() is not None


def status() -> dict:
    ok = available()
    return {"available": ok, "model": _model_name if ok else None, "error": None if ok else _error,
            "languages": sorted(LANGS)}


def model_name() -> str:
    return _model_name or "kokoro-82m"


_SENT = re.compile(r"(?<=[.!?…])\s+(?=[\"'“(\[]?[A-ZÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜÇÑ0-9¿¡])")


def split_sentences(text: str, max_chars: int = 220, first_max: int | None = None) -> list[str]:
    """Split for streaming playback: sentences, long ones cut at commas.
    `first_max` cuts the first chunk shorter (at a comma) so audio starts sooner."""
    out = []
    for s in _SENT.split(text.strip()):
        s = s.strip()
        while True:
            limit = first_max if (first_max and not out) else max_chars
            if len(s) <= limit or "," not in s[:limit]:
                break
            cut = s[:limit].rfind(",") + 1
            out.append(s[:cut].strip())
            s = s[cut:].strip()
        if s:
            out.append(s)
    return out


_CACHE: "OrderedDict[tuple, tuple[np.ndarray, int]]" = None  # type: ignore[assignment]


def synth_cached(text: str, language: str | None = None, voice: str | None = None) -> tuple[np.ndarray, int]:
    """Same as synth() with a small LRU cache (greetings and fillers repeat a lot)."""
    global _CACHE
    from collections import OrderedDict

    if _CACHE is None:
        _CACHE = OrderedDict()
    key = (text, (language or "en")[:2], voice)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    out = synth(text, language, voice)
    _CACHE[key] = out
    if len(_CACHE) > 64:
        _CACHE.popitem(last=False)
    return out


_MINUS = {"en": "minus", "es": "menos", "fr": "moins", "it": "meno", "pt": "menos"}
_PERCENT = {"en": " percent", "es": " por ciento", "fr": " pour cent", "it": " per cento", "pt": " por cento"}


def speakable(text: str, lang: str = "en") -> str:
    """Make money and signs read naturally without changing any number."""
    minus = _MINUS.get(lang, "minus")
    t = re.sub(r"(?<=\d)['’ ](?=\d{3})", "", text)            # 18'550 -> 18550
    t = re.sub(r"-\s?CHF\s?(\d)", minus + r" CHF \1", t)           # -CHF 3600
    t = re.sub(r"CHF\s?-\s?(\d)", minus + r" CHF \1", t)           # CHF -3600
    t = re.sub(r"(?<![\w\d])-(\d)", minus + r" \1", t)             # -3600 (not ranges like 1-3)
    t = t.replace("%", _PERCENT.get(lang, " percent"))
    return t


def synth(text: str, language: str | None = None, voice: str | None = None, speed: float = 1.0) -> tuple[np.ndarray, int]:
    k = _load()
    if k is None:
        raise RuntimeError(_error or "kokoro unavailable")
    lang = (language or "en")[:2].lower()
    klang, default_voice = LANGS.get(lang, LANGS["en"])
    if lang == "en":
        default_voice = DEFAULT_VOICE_EN
    voices = k.get_voices()
    v = voice if voice and voice in voices else (default_voice if default_voice in voices else "af_heart")
    spoken = speakable(text, lang)
    with _lock:
        samples, sr = k.create(spoken, voice=v, speed=speed, lang=klang)
    return samples, sr


def to_wav(samples: np.ndarray, sr: int) -> bytes:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return buf.getvalue()
