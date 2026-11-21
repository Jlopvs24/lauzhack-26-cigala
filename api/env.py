"""Load .env.local (gitignored) into os.environ without printing anything."""
from __future__ import annotations

import os
from pathlib import Path


def load_env() -> None:
    root = Path(__file__).resolve().parent.parent
    for name in (".env.local", ".env"):
        p = root / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
