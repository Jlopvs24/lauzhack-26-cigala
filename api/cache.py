"""Small thread-safe LRU cache for deterministic engine responses (/tree/expand, /tree/explore, /report).

Engine results are pure functions of the request (fixed seed), so identical requests can reuse the
response. Keyed by a hash of the route + canonical JSON body + engine version. Per process: with
`uvicorn --workers N` each worker keeps its own cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import OrderedDict
from typing import Any, Callable

MAX_ITEMS = int(os.environ.get("API_CACHE_ITEMS", "256"))


class LRU:
    def __init__(self, maxsize: int = MAX_ITEMS):
        self.maxsize = maxsize
        self._d: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str):
        with self._lock:
            if key in self._d:
                self._d.move_to_end(key)
                self.hits += 1
                return self._d[key]
            self.misses += 1
            return None

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._d[key] = value
            self._d.move_to_end(key)
            while len(self._d) > self.maxsize:
                self._d.popitem(last=False)

    def stats(self) -> dict:
        with self._lock:
            return {"items": len(self._d), "max_items": self.maxsize, "hits": self.hits, "misses": self.misses}


CACHE = LRU()
_inflight: dict[str, threading.Event] = {}
_inflight_lock = threading.Lock()


def key_for(route: str, body: dict, version: str = "") -> str:
    raw = json.dumps({"r": route, "b": body, "v": version}, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha1(raw.encode()).hexdigest()


def cached(route: str, body: dict, version: str, compute: Callable[[], Any]) -> tuple[Any, bool]:
    """Return (value, hit). Concurrent identical requests wait for the first one instead of recomputing."""
    k = key_for(route, body, version)
    v = CACHE.get(k)
    if v is not None:
        return v, True
    with _inflight_lock:
        ev = _inflight.get(k)
        leader = ev is None
        if leader:
            ev = _inflight[k] = threading.Event()
    if not leader:
        ev.wait(timeout=120)
        v = CACHE.get(k)
        if v is not None:
            return v, True
    try:
        v = compute()
        CACHE.put(k, v)
        return v, False
    finally:
        if leader:
            with _inflight_lock:
                _inflight.pop(k, None)
            ev.set()


class TTLValue:
    """One value recomputed at most every `ttl` seconds; concurrent callers share one computation."""

    def __init__(self, ttl: float):
        self.ttl = ttl
        self._value: Any = None
        self._at = 0.0
        self._lock = threading.Lock()

    def get(self, compute: Callable[[], Any], refresh: bool = False) -> tuple[Any, float, bool]:
        """Return (value, age_seconds, hit)."""
        import time

        with self._lock:  # held while computing: a second caller waits and then reuses the fresh value
            now = time.monotonic()
            hit = not (refresh or self._value is None or now - self._at > self.ttl)
            if not hit:
                self._value = compute()
                self._at = time.monotonic()
            return self._value, round(time.monotonic() - self._at, 1), hit
