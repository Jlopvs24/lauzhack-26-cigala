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
# Default: an open-weight Qwen (Apache-2.0, weights on Hugging Face: Qwen/Qwen3.6-35B-A3B, ~3B active parameters),
# so the same model can be self-hosted (LLM_BASE_URL). Fallbacks, only when a call fails: Qwen's API-only flash
# model, then a proprietary model. Override with AGENT_MODEL / AGENT_FALLBACK_MODELS.
DEFAULT_MODEL = "qwen/qwen3.6-35b-a3b"
DEFAULT_FALLBACKS = ["qwen/qwen3.7-flash", "anthropic/claude-haiku-5.5"]


def _target(force_openrouter: bool = False) -> tuple[str, dict, bool]:
    """(chat-completions URL, headers, is_custom). LLM_BASE_URL points every chat call at any OpenAI-compatible
    server (vLLM, Ollama, llama.cpp...) running the same open-weight model; LLM_API_KEY is optional there."""
    base = os.environ.get("LLM_BASE_URL", "").strip()
    if base and not force_openrouter:
        key = os.environ.get("LLM_API_KEY", "")
        return base.rstrip("/") + "/chat/completions", ({"Authorization": f"Bearer {key}"} if key else {}), True
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    return OPENROUTER_URL, {"Authorization": f"Bearer {key}", "X-Title": "cigala-lauzhack"}, False


def _adapt(body: dict, custom: bool) -> dict:
    """Drop OpenRouter-only fields for a self-hosted endpoint (server-side fallback list, usage accounting)."""
    if custom:
        for k in ("models", "usage", "reasoning"):
            body.pop(k, None)
    return body
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


# ------------------------------------------------------------------ hard spend guard
# The OpenRouter key has a small budget. Every paid call (this process and the other uvicorn workers, which all
# append to usage.jsonl) counts towards today's spend; past LLM_DAILY_BUDGET_USD every LLM call raises
# BudgetExceeded, and callers fall back to templates / clarifying questions. Engine routes are unaffected.
DAILY_BUDGET_USD = float(os.environ.get("LLM_DAILY_BUDGET_USD", "2.0"))
_spent_cache = {"at": 0.0, "day": "", "usd": 0.0}
_spent_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


def spent_today(max_age_s: float = 5.0) -> float:
    """USD spent today (local date) by all API processes, from usage.jsonl (re-read at most every few seconds)."""
    day = time.strftime("%Y-%m-%d")
    with _spent_lock:
        if _spent_cache["day"] == day and time.time() - _spent_cache["at"] < max_age_s:
            return _spent_cache["usd"]
        total = 0.0
        try:
            with USAGE_LOG.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if time.strftime("%Y-%m-%d", time.localtime(rec.get("ts", 0))) == day:
                        total += float(rec.get("cost_usd") or 0.0)
        except OSError:
            total = USAGE.cost_usd  # no log file: this process's own spend
        _spent_cache.update(at=time.time(), day=day, usd=total)
        return total


def budget() -> dict:
    spent = spent_today()
    return {"daily_limit_usd": DAILY_BUDGET_USD, "spent_today_usd": round(spent, 6),
            "remaining_usd": round(max(DAILY_BUDGET_USD - spent, 0.0), 6), "exceeded": spent >= DAILY_BUDGET_USD}


def _check_budget() -> None:
    if spent_today() >= DAILY_BUDGET_USD:
        raise BudgetExceeded(f"daily LLM budget of USD {DAILY_BUDGET_USD:.2f} reached; answering from templates")


def available() -> bool:
    """An endpoint is configured (OpenRouter key or LLM_BASE_URL) and today's budget is not exhausted (so callers
    go straight to their template fallback)."""
    if not os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("LLM_BASE_URL"):
        return False
    try:
        _check_budget()
    except BudgetExceeded:
        return False
    return True


def models() -> list[str]:
    primary = os.environ.get("AGENT_MODEL", DEFAULT_MODEL)
    fb = os.environ.get("AGENT_FALLBACK_MODELS")
    fallbacks = [m.strip() for m in fb.split(",")] if fb else DEFAULT_FALLBACKS
    return [primary] + [m for m in fallbacks if m and m != primary]


def chat(messages: list[dict], tools: list[dict] | None = None, model: str | None = None,
         purpose: str = "agent", timeout: float = 30.0, force_openrouter: bool = False, **params) -> dict:
    """One completion. Returns {message, model, cost_usd, prompt_tokens, completion_tokens, latency_ms}.

    Uses OpenRouter's `models` list for server-side fallback. Raises on HTTP/network error.
    """
    url, headers, custom = _target(force_openrouter)
    _check_budget()
    chain = [model] if model else models()
    body = {"model": chain[0], "messages": messages, "usage": {"include": True}, **params}
    if len(chain) > 1:
        body["models"] = chain
    if tools:
        body["tools"] = tools
    _adapt(body, custom)
    t0 = time.perf_counter()
    r = httpx.post(url, json=body, timeout=timeout, headers=headers)
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


def chat_stream(messages: list[dict], tools: list[dict] | None = None, model: str | None = None,
                purpose: str = "agent", timeout: float = 30.0, force_openrouter: bool = False, **params):
    """Streaming completion. Yields ("content", text_delta) as tokens arrive, then one
    ("final", {message: {content, tool_calls}, model, cost_usd, prompt_tokens, completion_tokens, latency_ms,
    first_token_ms}). Tool-call deltas are assembled. Raises on HTTP/network error."""
    url, headers, custom = _target(force_openrouter)
    _check_budget()
    chain = [model] if model else models()
    body = {"model": chain[0], "messages": messages, "usage": {"include": True}, "stream": True, **params}
    if len(chain) > 1:
        body["models"] = chain
    if tools:
        body["tools"] = tools
    t0 = time.perf_counter()
    first = None
    content, calls, used_model, usage = [], {}, chain[0], {}
    _adapt(body, custom)
    with httpx.stream("POST", url, json=body, timeout=timeout, headers=headers) as r:
        if r.status_code != 200:
            raise RuntimeError(f"openrouter {r.status_code}: {r.read()[:300]!r}")
        for line in r.iter_lines():
            if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                continue
            try:
                d = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            if "error" in d:
                raise RuntimeError(f"openrouter error: {str(d['error'])[:300]}")
            used_model = d.get("model") or used_model
            if d.get("usage"):
                usage = d["usage"]
            for ch in d.get("choices") or []:
                delta = ch.get("delta") or {}
                if delta.get("content"):
                    if first is None:
                        first = int((time.perf_counter() - t0) * 1000)
                    content.append(delta["content"])
                    yield "content", delta["content"]
                for tc in delta.get("tool_calls") or []:
                    slot = calls.setdefault(tc.get("index", 0), {"id": None, "type": "function",
                                                                 "function": {"name": "", "arguments": ""}})
                    slot["id"] = tc.get("id") or slot["id"]
                    fn = tc.get("function") or {}
                    slot["function"]["name"] += fn.get("name") or ""
                    slot["function"]["arguments"] += fn.get("arguments") or ""
    latency = int((time.perf_counter() - t0) * 1000)
    rec = {"ts": time.time(), "purpose": purpose, "model": used_model,
           "cost_usd": float(usage.get("cost") or 0.0), "prompt_tokens": int(usage.get("prompt_tokens") or 0),
           "completion_tokens": int(usage.get("completion_tokens") or 0), "latency_ms": latency}
    USAGE.add(rec)
    tool_calls = [calls[i] for i in sorted(calls)] or None
    yield "final", {"message": {"content": "".join(content), "tool_calls": tool_calls}, **rec,
                    "first_token_ms": first}
