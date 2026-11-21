"""Minimal OpenRouter chat client with per-call cost/token logging.

Cost comes from OpenRouter's own accounting (usage.include=true), not estimated.
Calls are appended to api/usage.jsonl (gitignored) and summed in USAGE.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

import httpx

log = logging.getLogger("api.llm")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Small, cheap models with tool calling. Override with AGENT_MODEL / AGENT_FALLBACK_MODELS.
DEFAULT_MODEL = "qwen/qwen3.7-flash"
DEFAULT_FALLBACKS = ["openai/gpt-6-luna", "anthropic/claude-haiku-5.5"]
USAGE_LOG = Path(__file__).parent / "usage.jsonl"


class Usage:
    def __init__(self):
        self._lock = threading.Lock()
        self.calls = 0
        self.cost_usd = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.by_model: dict[str, dict] = {}

    def add(self, rec: dict) -> None:
        with self._lock:
            self.calls += 1
            self.cost_usd += rec.get("cost_usd", 0.0)
            self.prompt_tokens += rec.get("prompt_tokens", 0)
            self.completion_tokens += rec.get("completion_tokens", 0)
            m = self.by_model.setdefault(rec["model"], {"calls": 0, "cost_usd": 0.0})
            m["calls"] += 1
            m["cost_usd"] += rec.get("cost_usd", 0.0)
        try:
            with USAGE_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        except OSError:
            pass

    def summary(self) -> dict:
        with self._lock:
            return {"calls": self.calls, "cost_usd": round(self.cost_usd, 6),
                    "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                    "by_model": {k: {**v, "cost_usd": round(v["cost_usd"], 6)} for k, v in self.by_model.items()}}


USAGE = Usage()


def available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def models() -> list[str]:
    primary = os.environ.get("AGENT_MODEL", DEFAULT_MODEL)
    fb = os.environ.get("AGENT_FALLBACK_MODELS")
    fallbacks = [m.strip() for m in fb.split(",")] if fb else DEFAULT_FALLBACKS
    return [primary] + [m for m in fallbacks if m and m != primary]


def chat(messages: list[dict], tools: list[dict] | None = None, model: str | None = None,
         purpose: str = "agent", timeout: float = 30.0, **params) -> dict:
    """One completion. Returns {message, model, cost_usd, prompt_tokens, completion_tokens, latency_ms}.

    Uses OpenRouter's `models` list for server-side fallback. Raises on HTTP/network error.
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    chain = [model] if model else models()
    body = {"model": chain[0], "messages": messages, "usage": {"include": True}, **params}
    if len(chain) > 1:
        body["models"] = chain
    if tools:
        body["tools"] = tools
    t0 = time.perf_counter()
    r = httpx.post(OPENROUTER_URL, json=body, timeout=timeout,
                   headers={"Authorization": f"Bearer {key}", "X-Title": "cigala-lauzhack"})
    latency = int((time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        raise RuntimeError(f"openrouter {r.status_code}: {r.text[:300]}")
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"openrouter error: {str(data['error'])[:300]}")
    u = data.get("usage") or {}
    rec = {"ts": time.time(), "purpose": purpose, "model": data.get("model", chain[0]),
           "cost_usd": float(u.get("cost") or 0.0), "prompt_tokens": int(u.get("prompt_tokens") or 0),
           "completion_tokens": int(u.get("completion_tokens") or 0), "latency_ms": latency}
    USAGE.add(rec)
    log.info("llm %s %s $%.6f %d+%d tok %d ms", purpose, rec["model"], rec["cost_usd"],
             rec["prompt_tokens"], rec["completion_tokens"], latency)
    return {"message": data["choices"][0]["message"], **rec}
