"""cigala API (thread 2). Run: uvicorn api.main:app --reload --port 8000

Every response carries cost_usd, latency_ms and model (frugality metrics for AXA).
Engine calls cost 0 and have model = "engine:<core|mock>".
"""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from api import engine
from api.env import load_env

load_env()

from api import agent, voice  # noqa: E402  (need env loaded)

ALEXIA = engine.default_profile()

app = FastAPI(title="cigala API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


class ExpandReq(Loose):
    profile: dict[str, Any] | None = Field(None, description="Profile (contracts.md). Omit to use Alexia.")
    path: list[str] = Field(default_factory=list, description='Chosen node ids, e.g. ["1", "1.2"]. [] = root.')
    assumptions: list[dict[str, Any]] = Field(default_factory=list, description="Overrides: [{id, value}]")
    weather: list[str] = Field(default_factory=list, description="recession | inflation | market_crash | job_loss")


class SimulateReq(Loose):
    profile: dict[str, Any] | None = None
    node: dict[str, Any]
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    weather: list[str] = Field(default_factory=list)


class AskReq(Loose):
    question: str
    context: dict[str, Any] = Field(default_factory=dict,
                                    description="{profile, path, node_id, assumptions, weather, language, history}")


class TTSReq(Loose):
    text: str
    language: str | None = None
    voice: str | None = None


def _meta(t0: float, cost: float = 0.0, model: str | None = None) -> dict:
    return {"cost_usd": round(cost, 6), "latency_ms": int((time.perf_counter() - t0) * 1000),
            "model": model or f"engine:{engine.ENGINE_NAME}"}


@app.get("/health")
def health():
    return {"ok": True, "engine": engine.ENGINE_NAME, "llm": agent.llm_status(), "voice": voice.status()}


@app.get("/profiles/demo")
def demo_profile():
    return {"profile": ALEXIA}


@app.post("/tree/expand")
def tree_expand(req: ExpandReq):
    t0 = time.perf_counter()
    try:
        out = engine.expand(req.profile, req.path, req.assumptions, req.weather)
    except (KeyError, ValueError) as e:
        raise HTTPException(422, f"bad path: {e}") from e
    return {**out, "engine": engine.ENGINE_NAME, **_meta(t0)}


@app.post("/simulate")
def simulate(req: SimulateReq):
    t0 = time.perf_counter()
    try:
        res = engine.simulate(req.profile, req.node, req.assumptions, req.weather)
    except (KeyError, ValueError) as e:
        raise HTTPException(422, str(e)) from e
    return {"result": res, **_meta(t0)}


@app.get("/assumptions")
def assumptions():
    return {"assumptions": engine.assumptions()}


@app.post("/profiles/extract")
async def profiles_extract(files: list[UploadFile] | None = File(None), text: str | None = Form(None)):
    """Placeholder until multimodal/ (thread 3) ships: returns Alexia with provenance marked as mock."""
    t0 = time.perf_counter()
    received = [f.filename for f in files or []]
    profile = json.loads(json.dumps(ALEXIA))
    profile["provenance"] = {k: {"source": "mock", "confidence": 0.0}
                             for k in ("cash", "monthly_net_income", "monthly_rent", "monthly_other_expenses")}
    return {"profile": profile, "received_files": received, "received_text": bool(text),
            "extractor": "mock", **_meta(t0, model="mock")}


@app.post("/agent/ask")
def agent_ask(req: AskReq):
    t0 = time.perf_counter()
    ctx = dict(req.context)
    if not ctx.get("profile"):
        ctx["profile"] = ALEXIA
    out = agent.ask(req.question, ctx)
    return {**out, "latency_ms": int((time.perf_counter() - t0) * 1000)}


@app.post("/voice/stt")
async def voice_stt(audio: UploadFile = File(...), language: str | None = Form(None)):
    """Fallback STT for browsers without SpeechRecognition. WAV or MP3 is safest."""
    t0 = time.perf_counter()
    data = await audio.read()
    try:
        out = voice.stt(data, audio.filename or "audio.wav", language, audio.content_type)
    except (voice.VoiceError, RuntimeError) as e:
        raise HTTPException(503, f"stt unavailable: {e}") from e
    return {**out, "latency_ms": int((time.perf_counter() - t0) * 1000)}


@app.post("/voice/ask")
async def voice_ask(audio: UploadFile = File(...), context: str = Form("{}"), language: str | None = Form(None)):
    """Voice note -> STT -> agent, in one round trip. `context` is the /agent/ask context as a JSON string."""
    t0 = time.perf_counter()
    data = await audio.read()
    try:
        heard = voice.stt(data, audio.filename or "audio.wav", language, audio.content_type)
    except (voice.VoiceError, RuntimeError) as e:
        raise HTTPException(503, f"stt unavailable: {e}") from e
    try:
        ctx = json.loads(context or "{}")
    except json.JSONDecodeError as e:
        raise HTTPException(422, "context must be a JSON object") from e
    if not ctx.get("profile"):
        ctx["profile"] = ALEXIA
    if heard.get("language") and not ctx.get("language"):
        ctx["language"] = heard["language"]
    out = agent.ask(heard["text"], ctx)
    return {**out, "transcript": heard["text"], "stt": {k: heard.get(k) for k in ("model", "cost_usd", "provider_latency_ms")},
            "cost_usd": round(out["cost_usd"] + heard["cost_usd"], 6),
            "latency_ms": int((time.perf_counter() - t0) * 1000)}


@app.post("/voice/tts")
def voice_tts(req: TTSReq):
    t0 = time.perf_counter()
    try:
        audio, meta = voice.tts(req.text, req.language, req.voice)
    except (voice.VoiceError, RuntimeError) as e:
        raise HTTPException(503, str(e)) from e
    headers = {"X-Cost-USD": str(meta["cost_usd"]), "X-Model": meta["model"],
               "X-Latency-Ms": str(int((time.perf_counter() - t0) * 1000)),
               "Access-Control-Expose-Headers": "X-Cost-USD, X-Model, X-Latency-Ms"}
    return Response(content=audio, media_type=meta.get("media_type", "audio/mpeg"), headers=headers)


@app.get("/usage")
def usage():
    """Cumulative LLM/voice spend since the server started (AXA frugality panel)."""
    from api.llm import USAGE
    return USAGE.summary()
