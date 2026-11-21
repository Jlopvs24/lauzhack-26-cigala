"""Lumi Live (api/live.py): token route, WebSocket proxy and tool execution, with a fake Gemini Live socket."""
import asyncio
import base64
import json
import os

import pytest
from fastapi.testclient import TestClient

os.environ["OPENROUTER_API_KEY"] = ""
os.environ["TOGETHER_API_KEY"] = ""
os.environ["TTS_IN_PROCESS"] = "1"
os.environ["API_WARM"] = "0"

from api import live, llm  # noqa: E402
from api.main import app  # noqa: E402

c = TestClient(app)
CTX = {"path": ["2"], "node_id": "2", "language": "en"}


class FakeUpstream:
    """Scripted Gemini Live: setupComplete; a text turn -> toolCall(what_would_fix_it); the tool response -> audio,
    transcription, usage and turnComplete. Records everything the proxy sends."""

    def __init__(self):
        self.sent: list[dict] = []
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.closed = False

    async def send(self, raw):
        m = json.loads(raw)
        self.sent.append(m)
        if "setup" in m:
            await self.inbox.put({"setupComplete": {}})
        elif "realtimeInput" in m and "text" in m["realtimeInput"] and "Greet" not in m["realtimeInput"]["text"]:
            await self.inbox.put({"toolCall": {"functionCalls": [
                {"id": "fc1", "name": "what_would_fix_it", "args": {"node_id": "2"}},
                {"id": "fc2", "name": "get_current_node", "args": {}}]}})
        elif "toolResponse" in m:
            pcm = (b"\x10\x00" * 2400)
            await self.inbox.put({"serverContent": {"modelTurn": {"parts": [
                {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}})
            await self.inbox.put({"serverContent": {"outputTranscription": {"text": "If you take option 2, then"}}})
            await self.inbox.put({"serverContent": {"outputTranscription": {"text": " it needs financing."}}})
            await self.inbox.put({"serverContent": {"turnComplete": True}, "usageMetadata": {
                "promptTokenCount": 1000, "responseTokenCount": 200,
                "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 1000}],
                "responseTokensDetails": [{"modality": "AUDIO", "tokenCount": 200}]}})

    async def recv(self):
        return json.dumps(await self.inbox.get())

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed:
            raise StopAsyncIteration
        return await self.recv()

    async def close(self):
        self.closed = True


@pytest.fixture
def fake(monkeypatch):
    up = FakeUpstream()

    async def connect(url):
        assert "key=test-key" in url
        return up

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(live, "connect_upstream", connect)
    monkeypatch.setattr(llm.USAGE, "add", lambda rec: up.sent.append({"_usage": rec}))
    return up


def test_status_without_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    j = c.get("/live/status").json()
    assert j["available"] is False and j["reason"] == "no_key" and "Google" in j["privacy"]
    t = c.post("/live/token", json={"context": CTX}).json()
    assert t["available"] is False and "token" not in t


def test_token_returns_config_not_key(fake):
    r = c.post("/live/token", json={"context": CTX, "language": "es"})
    assert r.status_code == 200
    j = r.json()
    assert j["available"] and j["mode"] == "proxy" and j["ws_path"].startswith("/live/ws?token=")
    assert "test-key" not in r.text
    cfg = j["config"]
    assert cfg["language"] == "es" and "Spanish" in cfg["system_instruction"]
    sysmsg = cfg["system_instruction"]
    assert "NEVER recommend" in sysmsg and "if-then" in sysmsg and "Scope" in sysmsg and "Numbers: only from" in sysmsg
    assert {"get_node", "compare_nodes", "what_if", "what_would_fix_it", "get_current_node",
            "explain_assumption"} <= set(cfg["tools"])
    assert "propose_personalization" not in cfg["tools"]


def test_token_refused_over_budget(fake, monkeypatch):
    monkeypatch.setattr(llm, "spent_today", lambda *a, **k: 999.0)
    j = c.post("/live/token", json={"context": CTX}).json()
    assert j["available"] is False and j["reason"] == "budget"


def test_ws_rejects_bad_token(fake):
    with c.websocket_connect("/live/ws?token=nope") as ws:
        assert ws.receive_json()["type"] == "error"
        assert ws.receive_json() == {"type": "ended", "reason": "error"}


def test_ws_proxy_text_turn_runs_engine_tools(fake):
    tok = c.post("/live/token", json={"context": CTX}).json()
    with c.websocket_connect(tok["ws_path"]) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready" and ready["model"] == tok["model"]
        ws.send_bytes(b"\x00\x01" * 160)  # mic audio is forwarded as base64 PCM 16 kHz
        ws.send_json({"type": "text", "text": "What would fix this branch?"})
        tools, audio, captions, done = [], b"", "", None
        while done is None:
            m = ws.receive()
            if m.get("bytes"):
                audio += m["bytes"]
                continue
            d = json.loads(m["text"])
            if d["type"] == "tool":
                tools.append(d)
            elif d["type"] == "caption":
                captions += d["text"]
            elif d["type"] == "turn_complete":
                done = d
        assert [t["name"] for t in tools] == ["what_would_fix_it", "get_current_node"] and all(t["ok"] for t in tools)
        assert len(audio) == 4800
        assert captions == "If you take option 2, then it needs financing."
        assert done["grounding"]["grounded"] is True
        ws.send_json({"type": "context", "context": {"path": ["1"], "node_id": "1"}})
        ws.send_json({"type": "end"})
        while (d := ws.receive_json())["type"] != "ended":
            pass
        assert d["reason"] == "user_ended"

    setup = next(m["setup"] for m in fake.sent if "setup" in m)
    assert setup["model"].startswith("models/") and setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    names = {f["name"] for f in setup["tools"][0]["functionDeclarations"]}
    assert "what_would_fix_it" in names and "get_current_node" in names
    audio_in = [m for m in fake.sent if "audio" in m.get("realtimeInput", {})]
    assert audio_in and audio_in[0]["realtimeInput"]["audio"]["mimeType"] == "audio/pcm;rate=16000"
    # tool results come from our engine, with the user's context (node 2)
    resp = next(m["toolResponse"] for m in fake.sent if "toolResponse" in m)["functionResponses"]
    assert [r["id"] for r in resp] == ["fc1", "fc2"]
    assert resp[1]["response"]["node_id"] == "2" and "final_net_worth" in resp[1]["response"]
    assert "error" not in resp[0]["response"]
    note = [m for m in fake.sent if "clientContent" in m]
    assert note and note[0]["clientContent"]["turnComplete"] is False
    assert "node 1" in note[0]["clientContent"]["turns"][0]["parts"][0]["text"]
    usage = next(m["_usage"] for m in fake.sent if "_usage" in m)
    assert usage["purpose"] == "live" and usage["tool_calls"] == 2 and usage["cost_usd"] > 0
    assert usage["end_reason"] == "user_ended"


def test_token_is_one_use_and_one_session_at_a_time(fake, monkeypatch):
    tok = c.post("/live/token", json={"context": CTX}).json()
    monkeypatch.setitem(live._active, "n", 1)  # another session open
    assert c.get("/live/status").json()["reason"] == "busy"
    with c.websocket_connect(tok["ws_path"]) as ws:
        assert ws.receive_json()["type"] == "error"
        assert ws.receive_json()["reason"] == "busy"
    monkeypatch.setitem(live._active, "n", 0)
    with c.websocket_connect(tok["ws_path"]) as ws:  # already used
        assert "invalid" in ws.receive_json()["message"]


def test_tools_follow_context_updates():
    t = live.LiveTools(live._ctx(CTX, "en"))
    assert t.run("get_current_node", {})["node_id"] == "2"
    t.set_context(live._ctx({**CTX, "path": ["1"], "node_id": "1"}, "en"))
    assert t.run("get_current_node", {})["node_id"] == "1"
    a = t.run("get_assumptions", {})["assumptions"][0]
    assert t.run("explain_assumption", {"assumption_id": a["id"]})["id"] == a["id"]
    assert "error" in t.run("explain_assumption", {"assumption_id": "nope"})
    assert "error" in t.run("propose_personalization", {"node_id": "1", "text": "x"})  # not exposed in Live


def test_cost_of_usage():
    u = {"promptTokenCount": 1_000_000, "responseTokenCount": 1_000_000,
         "promptTokensDetails": [{"modality": "AUDIO", "tokenCount": 1_000_000}],
         "responseTokensDetails": [{"modality": "AUDIO", "tokenCount": 1_000_000}]}
    assert live.cost_of(u) == pytest.approx(live._PRICE[("prompt", "AUDIO")] + live._PRICE[("response", "AUDIO")])
