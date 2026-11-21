"""Minimal OpenRouter / Together client with per-call cost + latency logging.

Every paid call is appended to multimodal/benchmark/results/spend_log.jsonl
(model, tokens, USD cost as reported by OpenRouter, latency) so the AXA budget
is auditable. Keys are read from .env.local and never printed.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env.local")
SPEND_LOG = ROOT / "multimodal" / "benchmark" / "results" / "spend_log.jsonl"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TOGETHER_URL = "https://api.together.xyz/v1"


@dataclass
class LLMResult:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    seconds: float
    data: dict | None = None  # parsed JSON


def image_part(img, fmt="JPEG", quality=85) -> dict:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode()
    mime = "image/jpeg" if fmt == "JPEG" else "image/png"
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def parse_json(text: str) -> dict | None:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def chat(model: str, messages: list, *, tag: str = "", max_tokens: int = 600, json_mode: bool = True,
         temperature: float = 0.0, reasoning_effort: str | None = None, timeout: float = 90) -> LLMResult:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY missing (put it in .env.local)")
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
            "usage": {"include": True}}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if reasoning_effort:
        body["reasoning"] = {"effort": reasoning_effort}
    t0 = time.perf_counter()
    last = None
    for attempt in range(3):
        try:
            r = httpx.post(OPENROUTER_URL, json=body, timeout=timeout,
                           headers={"Authorization": f"Bearer {key}", "X-Title": "cigala-lauzhack"})
            if r.status_code == 200 and "choices" in r.json():
                break
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code == 400 and json_mode and "response_format" in r.text:
                body.pop("response_format", None)
        except httpx.HTTPError as e:
            last = repr(e)
        time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"{model} failed: {last}")
    dt = time.perf_counter() - t0
    j = r.json()
    u = j.get("usage") or {}
    content = j["choices"][0]["message"].get("content") or ""
    res = LLMResult(content, j.get("model", model), u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
                    float(u.get("cost") or 0.0), dt)
    res.data = parse_json(content)
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEND_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tag": tag, "model": model,
                            "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
                            "cost_usd": res.cost_usd, "seconds": round(dt, 3)}) + "\n")
    return res


def total_spend() -> float:
    if not SPEND_LOG.exists():
        return 0.0
    return sum(json.loads(l)["cost_usd"] for l in SPEND_LOG.read_text(encoding="utf-8").splitlines() if l.strip())
