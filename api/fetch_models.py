"""Download the local TTS model (Kokoro-82M, Apache-2.0) into api/models/ (gitignored).

python -m api.fetch_models          # int8 model (88 MB) + voices (27 MB)
python -m api.fetch_models --fp32   # fp32 model (310 MB), faster on most x86 CPUs
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
DEST = Path(__file__).parent / "models"


def fetch(name: str) -> None:
    out = DEST / name
    if out.exists() and out.stat().st_size > 1_000_000:
        print(f"ok {name} (already there)")
        return
    DEST.mkdir(exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    with httpx.stream("GET", BASE + name, follow_redirects=True, timeout=None) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.replace(out)
    print(f"downloaded {name} ({out.stat().st_size // 1_000_000} MB)")


if __name__ == "__main__":
    fetch("voices-v1.0.bin")
    fetch("kokoro-v1.0.onnx" if "--fp32" in sys.argv else "kokoro-v1.0.int8.onnx")
