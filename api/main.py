"""cigala API (thread 2). Run: uvicorn api.main:app --reload --port 8000

Every response carries cost_usd, latency_ms and model (frugality metrics for AXA).
Engine calls cost 0 and have model = "engine:<core|mock>".
"""
from __future__ import annotations

import base64
import json
import os
import logging
import time
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from api import cache, engine
from api.env import load_env

load_env()
log = logging.getLogger("api")

from api import agent, voice  # noqa: E402  (need env loaded)

ALEXIA = engine.default_profile()

app = FastAPI(title="cigala API", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(__import__("pathlib").Path(__file__).parent / "static")), name="static")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


class Personal(BaseModel):
    """Personal conditions (docs/plan.md "Personal conditions -> the tree re-grows"), forwarded to core."""
    custom_nodes: list[dict[str, Any]] = Field(default_factory=list, description=(
        "User-added branches: [{parent_id, node_id, label, description?, interventions[]}] (from /tree/personalize)"))
    node_patches: dict[str, list[dict[str, Any]]] = Field(default_factory=dict, description=(
        "Conditions added to existing nodes: {node_id: [interventions]}; inherited by the subtree"))


class ExpandReq(Loose, Personal):
    profile: dict[str, Any] | None = Field(None, description="Profile (contracts.md). Omit to use Alexia.")
    path: list[str] = Field(default_factory=list, description='Chosen node ids, e.g. ["1", "1.2"]. [] = root.')
    assumptions: list[dict[str, Any]] = Field(default_factory=list, description="Overrides: [{id, value}]")
    weather: list[Any] = Field(default_factory=list,
                               description='Named stress what-ifs: "recession" | "inflation" | "market_crash" | "job_loss" or {type, ...}')
    uncertainty: bool = Field(False, description="Optional Monte Carlo lens (bands). Off by default: results are "
                                                 "deterministic if-then paths.")
    exploration: bool = Field(False, description="Include the current node's exploration (break-even, goal-seek, "
                                                 "reverse stress, timing). Off by default for speed: fetch it with "
                                                 "POST /tree/explore when needed.")
    sensitivity: bool = Field(False, description="Include the current node's tornado. Off by default; "
                                                 "/tree/explore returns it.")


class SimulateReq(Loose, Personal):
    profile: dict[str, Any] | None = None
    node: dict[str, Any]
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    weather: list[Any] = Field(default_factory=list)
    uncertainty: bool = False


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


@app.on_event("startup")
def _warm_up() -> None:
    """Background warm-up: core's default tree (issue #33) and the TTS worker. Never blocks startup."""
    import threading

    def run():
        try:
            engine.warm()
        except Exception as e:  # noqa: BLE001
            log.warning("engine warm failed: %s", e)
        try:
            from api import tts_local
            tts_local.warm_worker()
        except Exception as e:  # noqa: BLE001
            log.warning("tts warm failed: %s", e)

    if os.environ.get("API_WARM", "1") == "1":
        threading.Thread(target=run, name="warm", daemon=True).start()


@app.get("/health")
def health():
    return {"ok": True, "engine": engine.ENGINE_NAME, "engine_version": engine.version(),
            "personal_conditions_supported": engine.supports_extras(),
            "llm_budget": __import__("api.llm", fromlist=["budget"]).budget(), "llm": agent.llm_status(),
            "voice": voice.status(), "cache": cache.CACHE.stats(), "pid": __import__("os").getpid()}


@app.get("/call", include_in_schema=False)
def call_prototype():
    """Realtime call prototype (api/static/call.html + call.js)."""
    return RedirectResponse("/static/call.html")


@app.get("/profiles/demo")
def demo_profile():
    return {"profile": ALEXIA}


def _engine_body(req: Loose, *fields: str) -> dict:
    body = {f: getattr(req, f) for f in fields}
    for f in ("custom_nodes", "node_patches"):  # personal conditions change every number: part of the key
        if getattr(req, f, None):
            body[f] = getattr(req, f)
    return body


def with_extras(route):
    """Run the route with the request's custom_nodes / node_patches applied to every engine call;
    501 if this core cannot take them yet."""
    import functools

    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        req = kwargs.get("req")
        src = req.context if isinstance(getattr(req, "context", None), dict) else req
        get = (lambda k: src.get(k)) if isinstance(src, dict) else (lambda k: getattr(src, k, None))
        try:
            with engine.using_extras(get("custom_nodes"), get("node_patches")):
                return route(*args, **kwargs)
        except engine.ExtrasNotSupported as e:
            raise HTTPException(501, str(e)) from e
    return wrapper


@app.post("/tree/expand")
@with_extras
def tree_expand(req: ExpandReq):
    """Visible tree. Cached by request (deterministic engine): repeated or concurrent identical calls are instant."""
    t0 = time.perf_counter()
    body = _engine_body(req, "profile", "path", "assumptions", "weather", "uncertainty", "exploration", "sensitivity")
    try:
        out, hit = cache.cached("/tree/expand", body, engine.version(), lambda: engine.expand(
            req.profile, req.path, req.assumptions, req.weather, uncertainty=req.uncertainty,
            exploration=req.exploration, sensitivity=req.sensitivity))
    except (KeyError, ValueError) as e:
        raise HTTPException(422, f"bad path: {e}") from e
    return {**out, "engine": engine.ENGINE_NAME, "uncertainty": req.uncertainty, "exploration": req.exploration,
            "personal_conditions": {"custom_nodes": len(req.custom_nodes), "patched_nodes": sorted(req.node_patches)},
            "uncertainty_flag_supported": engine.supports_uncertainty_flag(), "cached": hit, **_meta(t0)}


@app.post("/tree/explore")
@with_extras
def tree_explore(req: ExpandReq):
    """Exploration of the current node only (levers, break-even, goal-seek, reverse stress, timing, tornado),
    for clients that expand with exploration=false. Cached like /tree/expand."""
    t0 = time.perf_counter()
    body = _engine_body(req, "profile", "path", "assumptions", "weather")
    split = engine.explore_fn()

    def compute():
        if split:  # core's own split (issue #33), when it lands
            return split(req.profile, req.path, req.assumptions, req.weather)
        tree = engine.expand(req.profile, req.path, req.assumptions, req.weather, exploration=True, sensitivity=True)
        cur = next(n for n in tree["nodes"] if n["node_id"] == tree["current"])
        res = cur.get("result") or {}
        return {"node_id": cur["node_id"], "label": cur.get("label"), "exploration": res.get("exploration"),
                "sensitivity": res.get("sensitivity"), "trace_id": res.get("trace_id")}

    try:
        out, hit = cache.cached("/tree/explore", body, engine.version(), compute)
    except (KeyError, ValueError, StopIteration) as e:
        raise HTTPException(422, f"bad path: {e}") from e
    from api.agent import exploration_facts
    facts = [f["text"] for f in exploration_facts(out.get("exploration"), out.get("label"))]
    return {**out, "facts": facts, "cached": hit, **_meta(t0)}


@app.post("/simulate")
@with_extras
def simulate(req: SimulateReq):
    t0 = time.perf_counter()
    try:
        res = engine.simulate(req.profile, req.node, req.assumptions, req.weather, uncertainty=req.uncertainty)
    except (KeyError, ValueError) as e:
        raise HTTPException(422, str(e)) from e
    return {"result": res, **_meta(t0)}


@app.get("/assumptions")
def assumptions():
    return {"assumptions": engine.assumptions()}


_AUDIO_EXT = {"wav": "wav", "mp3": "mp3", "ogg": "ogg", "oga": "ogg", "webm": "ogg", "m4a": "m4a", "flac": "flac"}


def _extract_mock(names: list[str], text: str | None, reason: str) -> dict:
    profile = json.loads(json.dumps(ALEXIA))
    profile["provenance"] = {k: {"source": "mock", "method": "mock", "extractor": "mock", "confidence": 0.0,
                                 "grounded": False}
                             for k in ("cash", "monthly_net_income", "monthly_rent", "monthly_other_expenses")}
    return {"profile": profile, "extractor": "mock", "mock_reason": reason, "received_files": names,
            "received_text": bool(text), "missing_fields": [], "checks": [], "documents": [], "transcripts": []}


@app.post("/profiles/extract")
def profiles_extract(files: list[UploadFile] | None = File(None), text: str | None = Form(None),
                     audio: UploadFile | None = File(None), base_profile: str | None = Form(None),
                     strategy: str = Form("frugal")):
    """Documents (payslip, bank statement, rental contract: PDF/JPG/PNG), free text and/or a voice note
    -> Profile with per-field provenance, via multimodal.extract (thread 3).
    Audio can come as `audio` or among `files` (by extension/content type).
    Falls back to the mock (extractor "mock", `mock_reason`) only if multimodal's deps are missing."""
    t0 = time.perf_counter()
    docs, audio_bytes, audio_fmt = [], None, "wav"
    for f in files or []:
        name = f.filename or "upload"
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        data = f.file.read()
        if (f.content_type or "").startswith("audio/") or ext in _AUDIO_EXT:
            audio_bytes, audio_fmt = data, _AUDIO_EXT.get(ext, "wav")
        else:
            docs.append((name, data))
    if audio is not None:
        name = audio.filename or "voice.wav"
        audio_bytes = audio.file.read()
        audio_fmt = _AUDIO_EXT.get(name.rsplit(".", 1)[-1].lower(), "wav")
    text = (text or "").strip() or None
    if not docs and not text and not audio_bytes:
        raise HTTPException(422, "send at least one of: files, text, audio")
    try:
        base = json.loads(base_profile) if base_profile else None
    except json.JSONDecodeError as e:
        raise HTTPException(422, "base_profile must be a JSON object") from e

    try:
        from multimodal import extract
        out = extract(files=docs, text=text, audio=audio_bytes, audio_format=audio_fmt, strategy=strategy,
                      base_profile=base)
    except ImportError as e:  # multimodal deps not installed on this machine
        log.warning("multimodal unavailable, using mock: %s", e)
        out = _extract_mock([n for n, _ in docs], text, f"multimodal unavailable: {e}")
        _set_income_basis(out.get("profile"))
        return {**out, **_meta(t0, model="mock")}
    except Exception as e:  # noqa: BLE001
        log.exception("extract failed")
        raise HTTPException(502, f"extraction failed: {type(e).__name__}: {e}") from e
    _set_income_basis(out.get("profile"))
    _warm_profile(out.get("profile"))
    return {**out, "cost_usd": round(float(out.get("cost_usd") or 0), 6),
            "latency_ms": int((time.perf_counter() - t0) * 1000), "model": out.get("extractor")}


def _set_income_basis(profile: dict | None) -> None:
    """Profiles extracted from payslips/statements carry Swiss payslip net income (after social contributions,
    before income tax), so the engine still charges income tax: income_basis = "net_before_tax" (core #49).
    An extractor or base_profile that already states a basis wins. ("take_home" is only for profiles imported
    from the UBS synthetic CSV rows; no api/ path builds those.)"""
    if not isinstance(profile, dict):
        return
    profile.setdefault("income_basis", "net_before_tax")
    prov = profile.setdefault("provenance", {})
    if isinstance(prov, dict):
        prov.setdefault("income_basis", {"source": "api default: payslip net before income tax", "confidence": 1.0})


def _warm_profile(profile: dict | None) -> None:
    """A new profile was just extracted: precompute its tree in the background (~1 s) so the first clicks are instant."""
    if not profile:
        return
    import threading

    def run():
        try:
            engine.warm(profile)
        except Exception as e:  # noqa: BLE001
            log.warning("warm for new profile failed: %s", e)

    threading.Thread(target=run, name="warm-profile", daemon=True).start()


class ReportReq(Loose, Personal):
    profile: dict[str, Any] | None = Field(None, description="Profile; omit to use Alexia.")
    path: list[str] = Field(default_factory=list, description='Chosen node ids from the root, e.g. ["2", "2.1"].')
    assumptions: list[dict[str, Any]] = Field(default_factory=list, description="Overrides: [{id, value}]")
    uncertainty: bool = Field(False, description="Include the optional Monte Carlo lens (section 10).")
    language: str = Field("en", description="Language of the plain-language summary.")


@app.post("/report")
@with_extras
def report(req: ReportReq):
    """Path report (docs/report-spec.md §3): 12 structured sections, numbers only from the engine."""
    from api.report import build_report
    t0 = time.perf_counter()
    body = _engine_body(req, "profile", "path", "assumptions", "uncertainty")  # language: summary only
    try:
        out, hit = cache.cached("/report", body, engine.version(), lambda: build_report(
            req.profile, req.path, req.assumptions, req.uncertainty, req.language))
    except (KeyError, ValueError, StopIteration) as e:
        raise HTTPException(422, f"bad path: {e}") from e
    if hit:
        out = {**out, "cost_usd": 0.0, "latency_ms": int((time.perf_counter() - t0) * 1000)}
    return {**out, "cached": hit}


def _report_data(req: "ReportReq") -> dict:
    """The /report payload (same cache entry as POST /report)."""
    from api.report import build_report
    body = _engine_body(req, "profile", "path", "assumptions", "uncertainty")
    out, _ = cache.cached("/report", body, engine.version(), lambda: build_report(
        req.profile, req.path, req.assumptions, req.uncertainty, req.language))
    return out


@app.post("/report/summary")
@with_extras
def report_summary(req: ReportReq):
    """Grounded LLM rewording of the report's template summary, for the UI to swap in when it arrives.
    Same body as /report. Returns {text, mode: llm|template, template, language, model, cost_usd, cached,
    latency_ms, rejected_llm_numbers?}. Uses the frugal default model; any number not in the template means
    the template is returned instead. Cached by request."""
    from api.report import llm_summary
    t0 = time.perf_counter()
    body = _engine_body(req, "profile", "path", "assumptions", "uncertainty", "language")
    try:
        out, hit = cache.cached("/report/summary", body, engine.version(),
                                lambda: llm_summary(_report_data(req), req.language))
    except (KeyError, ValueError, StopIteration) as e:
        raise HTTPException(422, f"bad path: {e}") from e
    out = {**out, "language": req.language, "cached": hit,
           "latency_ms": int((time.perf_counter() - t0) * 1000)}
    if hit:
        out["cost_usd"] = 0.0
    return out


class PersonalizeReq(Loose, Personal):
    profile: dict[str, Any] | None = None
    path: list[str] = Field(default_factory=list, description='Chosen path, e.g. ["2"]')
    node_id: str | None = Field(None, description="Node the condition is about (default: last of path)")
    text: str | None = Field(None, description="The user's words, e.g. \"I'd get a CHF 600/month scholarship\"")
    audio_b64: str | None = Field(None, description="Voice note instead of text (base64); transcribed first")
    audio_format: str = Field("wav", description="wav | mp3 | ogg ...")
    language: str | None = None
    mode: str = Field("auto", description="patch | new_branch | auto")
    assumptions: list[dict[str, Any]] = Field(default_factory=list)


@app.post("/tree/personalize")
@with_extras
def tree_personalize(req: PersonalizeReq):
    """The user's own condition on a branch -> a proposed patch or new branch (never applied here).
    Returns {proposal: {mode, node_id | parent_id, node_id (new branch), label, description, interventions,
    apply}, explanation, clarifying_question, transcript?, language, cost_usd, latency_ms, model, validation}.
    Send `proposal.apply` back merged into node_patches / custom_nodes to re-grow the tree."""
    from api.personalize import personalize
    t0 = time.perf_counter()
    text, transcript, stt_cost = req.text, None, 0.0
    if req.audio_b64 and not text:
        import base64
        try:
            heard = voice.stt(base64.b64decode(req.audio_b64), f"voice.{req.audio_format}", req.language)
        except (voice.VoiceError, RuntimeError, ValueError) as e:
            raise HTTPException(503, f"stt unavailable: {e}") from e
        text, transcript, stt_cost = heard.get("text"), heard.get("text"), heard.get("cost_usd", 0.0)
        req.language = req.language or heard.get("language")
    if not text:
        raise HTTPException(422, "send text or audio_b64")
    try:
        out = personalize(req.profile, req.path, req.node_id, text, req.language, req.mode, req.assumptions)
    except (KeyError, ValueError) as e:
        raise HTTPException(422, f"bad node: {e}") from e
    if transcript is not None:
        out["transcript"] = transcript
    out["cost_usd"] = round(out.get("cost_usd", 0.0) + stt_cost, 6)
    out["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return out


# ------------------------------------------------------------------ combined decisions, surfaces, smallest change,
# timing scan (core #48 item 6). Deterministic, cached like /tree/expand, personal conditions forwarded.
class _AnalysisBase(Loose, Personal):
    profile: dict[str, Any] | None = None
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    weather: list[Any] = Field(default_factory=list)


class CombineReq(_AnalysisBase):
    a: str = Field(..., description='First node (its whole path), e.g. "3.2"')
    b: str = Field(..., description='Second node: its own decisions are added on top of a, e.g. "3.3"')


class SurfaceReq(_AnalysisBase):
    path: list[str] = Field(default_factory=list)
    x: str | dict[str, Any] = Field(..., description='Lever: an assumption id, {"assumption": id, "values"?} or '
                                                     '{"param", "op": "add"|"set", "range": [lo, hi] | "values", ...}')
    y: str | dict[str, Any]
    n: int = Field(7, ge=2, le=11)
    compare_to: str | None = Field(None, description="Peer node: cells gain delta_vs_peer (break-even line)")


class SmallestChangeReq(_AnalysisBase):
    path: list[str] = Field(default_factory=list)
    target: str = Field("no_funding_gap", description="no_funding_gap | feasible | holds")
    levers: list[dict[str, Any]] | None = None


class TimingScanReq(_AnalysisBase):
    path: list[str] = Field(default_factory=list)
    delays: list[int] | None = None


def _lever(v):
    return {"assumption": v} if isinstance(v, str) else v


def _analysis(route: str, req: _AnalysisBase, name: str, call) -> dict:
    t0 = time.perf_counter()
    fn = engine.core_fn(name)
    if fn is None:
        raise HTTPException(501, f"this engine has no core.{name} (core #48 item 6)")
    body = req.model_dump()
    extras = {k: v for k, v in (("custom_nodes", req.custom_nodes), ("node_patches", req.node_patches)) if v}
    try:
        out, hit = cache.cached(route, body, engine.version(), lambda: call(fn, extras))
    except (KeyError, ValueError) as e:
        raise HTTPException(422, str(e)) from e
    return {**out, "cached": hit, **_meta(t0)}


class CompareReq(_AnalysisBase):
    paths: list[list[str]] = Field(..., description='2-4 node paths from any branches, e.g. [["1"], ["2", "2.3"]]')
    baseline: str = Field("parent", description='Which delta goes in `delta`: "parent" (this option alone) or '
                                                '"today" (vs the status quo). Both are always in impact_alone.')


@app.post("/tree/compare")
@with_extras
def tree_compare(req: CompareReq):
    """Compare 2-4 options side by side: headline, plan check, key metrics, series, impact of the option's own
    decision (vs its parent and vs today) and per-metric orders. Deterministic, no LLM, cached."""
    from api.compare import compare
    t0 = time.perf_counter()
    if req.baseline not in ("parent", "today"):
        raise HTTPException(422, 'baseline must be "parent" or "today"')
    body = _engine_body(req, "profile", "paths", "assumptions", "weather", "baseline")
    try:
        out, hit = cache.cached("/tree/compare", body, engine.version(), lambda: compare(
            req.profile, req.paths, req.assumptions, req.weather, req.baseline))
    except (KeyError, ValueError) as e:
        raise HTTPException(422, str(e)) from e
    return {**out, "cached": hit, **_meta(t0)}


@app.post("/tree/combine")
def tree_combine(req: CombineReq):
    """Path to `a` plus `b`'s own decisions (conflicts listed, later wins), with a combined / A / B comparison."""
    return _analysis("/tree/combine", req, "combine", lambda fn, ex: fn(
        req.profile, req.a, req.b, assumptions=req.assumptions, weather=req.weather, **ex))


@app.post("/tree/surface")
def tree_surface(req: SurfaceReq):
    """2-lever grid (heatmap): cells[y][x] with plan level, net worth, min cash, optional delta_vs_peer."""
    return _analysis("/tree/surface", req, "surface", lambda fn, ex: fn(
        req.profile, req.path, _lever(req.x), _lever(req.y), n=req.n, compare_to=req.compare_to,
        assumptions=req.assumptions, weather=req.weather, **ex))


@app.post("/tree/smallest_change")
def tree_smallest_change(req: SmallestChangeReq):
    """What would fix this branch: per lever, the smallest change that reaches `target`, to the cent."""
    if req.target not in ("no_funding_gap", "feasible", "holds"):
        raise HTTPException(422, "target must be no_funding_gap, feasible or holds")
    from api.agent import smallest_change_facts
    out = _analysis("/tree/smallest_change", req, "smallest_change", lambda fn, ex: fn(
        req.profile, req.path, req.target, levers=req.levers, assumptions=req.assumptions, weather=req.weather, **ex))
    return {**out, "facts": smallest_change_facts(out)}


@app.post("/tree/timing_scan")
def tree_timing_scan(req: TimingScanReq):
    """The node's own decision started 0-36 months later: level and net worth per start, latest start that holds."""
    return _analysis("/tree/timing_scan", req, "timing_scan", lambda fn, ex: fn(
        req.profile, req.path, delays=req.delays, assumptions=req.assumptions, weather=req.weather, **ex))


@app.post("/agent/ask")
@with_extras
def agent_ask(req: AskReq):
    t0 = time.perf_counter()
    ctx = dict(req.context)
    if not ctx.get("profile"):
        ctx["profile"] = ALEXIA
    out = agent.ask(req.question, ctx)
    return {**out, "latency_ms": int((time.perf_counter() - t0) * 1000)}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/agent/ask/stream")
def agent_ask_stream(req: AskReq):
    """Server-Sent Events: `start` at once, then `sentence` events as soon as each sentence has passed the
    guards (grounded numbers, no advice, if-then wording), `replace` if a fallback text is used, and `done`
    with the same fields as /agent/ask. Each event: `event: <type>` + `data: <json>`."""
    ctx = dict(req.context)
    if not ctx.get("profile"):
        ctx["profile"] = ALEXIA

    def gen():
        # Starlette advances this generator step by step in copied contexts, so the personal conditions are
        # applied around each step (not across yields).
        it = agent.ask_stream(req.question, ctx)
        try:
            while True:
                with engine.using_extras(ctx.get("custom_nodes"), ctx.get("node_patches")):
                    try:
                        ev = next(it)
                    except StopIteration:
                        return
                yield _sse(ev["type"], ev)
        except engine.ExtrasNotSupported as e:
            yield _sse("error", {"type": "error", "error": str(e)})
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {"type": "error", "error": str(e)[:200]})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


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
    headers["X-Audio-Seconds"] = str(meta.get("audio_seconds", ""))
    headers["Access-Control-Expose-Headers"] += ", X-Audio-Seconds"
    return Response(content=audio, media_type=meta.get("media_type", "audio/mpeg"), headers=headers)


def _ndjson(obj: dict) -> str:
    return json.dumps(obj) + "\n"


@app.post("/voice/tts/stream")
def voice_tts_stream(req: TTSReq):
    """Sentence-by-sentence TTS as NDJSON, so playback starts after the first sentence.

    Lines: {"index", "text", "audio_b64" (WAV), "media_type", "audio_seconds", "synth_ms", "model", "cost_usd"}
    then {"done": true, "sentences", "cost_usd", "latency_ms"}. Errors: {"error": "..."} (client falls back
    to browser speechSynthesis for the rest). 503 up front if no server TTS is available.
    """
    if voice.tts_provider() is None:
        raise HTTPException(503, "server TTS unavailable: use the browser speechSynthesis")
    from api.tts_local import split_sentences

    sentences = split_sentences(req.text[:4000], first_max=90)
    t0 = time.perf_counter()

    def gen():
        total = 0.0
        for i, sent in enumerate(sentences):
            t1 = time.perf_counter()
            try:
                audio, meta = voice.tts(sent, req.language, req.voice)
            except (voice.VoiceError, RuntimeError) as e:
                yield _ndjson({"index": i, "error": str(e)})
                return
            total += meta["cost_usd"]
            yield _ndjson({"index": i, "text": sent, "audio_b64": base64.b64encode(audio).decode(),
                              "media_type": meta.get("media_type"), "audio_seconds": meta.get("audio_seconds"),
                              "synth_ms": int((time.perf_counter() - t1) * 1000), "model": meta["model"],
                              "cost_usd": meta["cost_usd"]})
        yield _ndjson({"done": True, "sentences": len(sentences), "cost_usd": round(total, 6),
                       "latency_ms": int((time.perf_counter() - t0) * 1000)})

    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


FILLERS = {
    "en": ["Let me check.", "Good question.", "One second."],
    "es": ["Déjame mirar.", "Buena pregunta.", "Un segundo."],
    "fr": ["Je regarde.", "Bonne question.", "Une seconde."],
}


@app.get("/voice/fillers")
def voice_fillers(language: str = "en"):
    """Short phrases the call client plays right after the user stops talking (cached TTS, instant)."""
    lang = language[:2].lower()
    return {"language": lang, "fillers": FILLERS.get(lang, FILLERS["en"])}


_VALIDATION = cache.TTLValue(ttl=float(os.environ.get("VALIDATION_TTL_S", "60")))


@app.get("/validation")
def validation(refresh: bool = False):
    """Live engine validation (core.validation): accounting identities on every node, reproducibility,
    monotonicity, isolation, UBS starter-kit match, verified threshold searches. Cached ~60 s
    (`age_s` says how old the run is); `?refresh=true` forces a new run."""
    t0 = time.perf_counter()
    fn = engine.validation_fn()
    if fn is None:
        raise HTTPException(503, "validation needs core with core.validation() (PR #40)")
    try:
        out, age, hit = _VALIDATION.get(fn, refresh=refresh)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"validation crashed: {type(e).__name__}: {e}") from e
    return {**out, "age_s": age, "cached": hit, **_meta(t0)}


@app.get("/usage")
def usage():
    """Cumulative LLM/voice spend since the server started (AXA frugality panel)."""
    from api.llm import USAGE, budget
    return {**USAGE.summary(), "budget": budget()}
