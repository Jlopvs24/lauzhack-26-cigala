"""API tests. Engine-agnostic: they must pass on the mock and on core/ (contracts v1).

Node ids, labels and assumption ids are read from responses, never hard-coded,
except the structural ids "0", "1", "2", "3" that both trees share.
"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ["OPENROUTER_API_KEY"] = ""  # tests never spend money: agent uses templates
os.environ["TOGETHER_API_KEY"] = ""

from api import engine  # noqa: E402
from api.agent import check_grounding  # noqa: E402
from api.main import app  # noqa: E402

c = TestClient(app)


def expand(**body):
    r = c.post("/tree/expand", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def by_id(j):
    return {n["node_id"]: n for n in j["nodes"]}


def weather_types(result):
    return [w["type"] if isinstance(w, dict) else w for w in result.get("weather") or []]


def test_health():
    j = c.get("/health").json()
    assert j["ok"] and j["engine"] == engine.ENGINE_NAME


def test_expand_root():
    j = expand(path=[])
    nodes = by_id(j)
    assert nodes["0"]["status"] == "chosen"
    children = [n for n in j["nodes"] if n["status"] == "child"]
    assert len(children) >= 2 and all(n["parent_id"] == "0" for n in children)
    for k in ("cost_usd", "latency_ms", "model", "current", "path", "assumptions"):
        assert k in j


def test_expand_prunes_and_results_are_consistent():
    root = expand(path=[])
    first = [n["node_id"] for n in root["nodes"] if n["status"] == "child"]
    pick = first[1]
    lvl1 = expand(path=[pick])
    kids = [n["node_id"] for n in lvl1["nodes"] if n["status"] == "child"]
    assert kids, "level-1 node should have children"
    j = expand(path=[pick, kids[0]])
    status = {n["node_id"]: n["status"] for n in j["nodes"]}
    assert status[pick] == "chosen" and status[kids[0]] == "chosen"
    assert all(status.get(k) == "sibling" for k in kids[1:])
    assert all(i not in status for i in first if i != pick)  # earlier siblings pruned
    assert j["current"] == kids[0]
    for n in j["nodes"]:
        r = n["result"]
        h = r["horizon_months"]
        assert all(ch["passed"] for ch in r["checks"]), (n["node_id"], r["checks"])
        assert len(r["deterministic"]["cash"]) == h + 1
        assert len(r["bands"]["net_worth"]["p50"]) == h + 1
        assert r["trace_id"]


def test_master_runs_short_in_month_7():
    """Both engines' Alexia master's path (node 2) runs out of cash in month 7 (index 6)."""
    m = by_id(expand(path=["2"]))["2"]["result"]["metrics"]
    assert m["first_negative_month"] == 6 and m["min_cash"] < 0


def test_ubs_starter_kit_numbers():
    master = {"name": "Master's degree",
              "phases": [{"start_month": 0, "end_month": 24, "monthly_income_chf": 1200, "monthly_expenses_chf": 2100},
                         {"start_month": 24, "end_month": 120, "monthly_income_chf": 4800, "monthly_expenses_chf": 3100}],
              "one_off_costs": [{"month": 0, "amount_chf": 2500}, {"month": 12, "amount_chf": 2500}]}
    if engine.ENGINE_NAME == "core":
        from core.starter import simulate_starter
        r = simulate_starter({"name": "Alexia", "opening_cash_chf": 8000, "horizon_months": 120}, master)
        cash = r["deterministic"]["cash"]
    else:
        cash = by_id(expand(path=["2"]))["2"]["result"]["deterministic"]["cash"]
    assert round(min(cash), 2) == -18600 and round(cash[-1], 2) == 144600


def test_bad_path():
    assert c.post("/tree/expand", json={"path": ["9.9"]}).status_code == 422


def test_assumption_override_and_weather():
    base = expand(path=["1"])
    aid = next(n for n in base["nodes"] if n["node_id"] == "1")["assumptions_ref"] or \
        [a["id"] for a in base["assumptions"]]
    aid = aid[0]
    cur = next(a for a in base["assumptions"] if a["id"] == aid)["value"]
    up = expand(path=["1"], assumptions=[{"id": aid, "value": cur * 1.5 + 100}], weather=["job_loss"])
    b, u = by_id(base)["1"]["result"], by_id(up)["1"]["result"]
    assert weather_types(u) == ["job_loss"]
    assert u["deterministic"]["net_worth"][-1] != b["deterministic"]["net_worth"][-1]


def test_simulate():
    j = c.post("/simulate", json={"node": {"node_id": "3"}}).json()
    assert j["result"]["node_id"] == "3"
    assert c.post("/simulate", json={"node": {"node_id": "9.9"}}).status_code == 422


def test_assumptions_route():
    a = c.get("/assumptions").json()["assumptions"]
    assert a and all({"id", "value", "source"} <= set(x) for x in a)


@pytest.mark.parametrize("lang,q", [("es", "¿Qué pasa si hago el máster?"), ("en", "What happens with the master?"),
                                    ("fr", "Qu'est-ce qui se passe si je fais le master ?")])
def test_agent_template(lang, q):
    j = c.post("/agent/ask", json={"question": q, "context": {"path": ["2"]}}).json()
    assert j["mode"] == "template" and j["language"] == lang
    assert "7" in j["answer"]  # month 7 shortfall
    assert j["cost_usd"] == 0 and j["grounding"]["grounded"]


def test_agent_defaults_to_english():
    j = c.post("/agent/ask", json={"question": "ok?", "context": {}}).json()
    assert j["language"] == "en"


def test_grounding():
    tools = [{"final_net_worth_p50": 143660.86, "min_cash": -18600.0, "label": "Take a CHF 15,000 study loan"}]
    assert check_grounding("Median CHF 143'661, lowest CHF -18'600 in 2029, loan CHF 15,000.", tools)["grounded"]
    assert not check_grounding("You would have CHF 250'000.", tools)["grounded"]
    assert check_grounding("With a salary of 3800 CHF...", tools, "what if 3800?")["grounded"]


def test_stt_without_key_is_503():
    assert c.post("/voice/stt", files={"audio": ("a.wav", b"RIFF", "audio/wav")}).status_code == 503


def test_tts_local_or_503():
    """Kokoro (local, free) when its model files exist, else 503 so the browser speaks."""
    from api import voice
    r = c.post("/voice/tts", json={"text": "Month 7, minus CHF 18'550."})
    if voice.tts_provider() is None:
        assert r.status_code == 503
        assert c.post("/voice/tts/stream", json={"text": "Hi."}).status_code == 503
        return
    assert r.status_code == 200 and r.content[:4] == b"RIFF"
    assert r.headers["x-cost-usd"] == "0.0"
    import json
    lines = [json.loads(x) for x in c.post("/voice/tts/stream", json={"text": "Hi. I am Lumi."}).text.splitlines()]
    assert [x.get("text") for x in lines[:-1]] == ["Hi.", "I am Lumi."] and lines[-1]["done"]


def test_speakable_keeps_numbers():
    from api.tts_local import speakable, split_sentences
    assert speakable("CHF -18'550 and 99.4%") == "minus CHF 18550 and 99.4 percent"
    assert speakable("CHF -18'550", "es") == "menos CHF 18550"
    assert speakable("months 1-3") == "months 1-3"
    assert split_sentences("Hi. It is 99.4% likely! Ok?") == ["Hi.", "It is 99.4% likely!", "Ok?"]


def test_call_prototype_served():
    r = c.get("/call", follow_redirects=True)
    assert r.status_code == 200 and "CharacterCall" in r.text
    assert c.get("/static/call.js").status_code == 200


def test_agent_call_mode_template():
    j = c.post("/agent/ask", json={"question": "why?", "context": {"path": ["2"], "mode": "call"}}).json()
    assert j["answer"] and j["cost_usd"] == 0


def test_extract_wires_multimodal(monkeypatch):
    import multimodal
    seen = {}

    def fake_extract(files=None, text=None, audio=None, audio_format="wav", strategy="frugal", base_profile=None):
        seen.update(files=[n for n, _ in files], text=text, audio=audio, audio_format=audio_format)
        return {"profile": {"cash": 8000, "provenance": {"cash": {"source": "bank_statement_pdf_text"}}},
                "extractor": "fake", "cost_usd": 0.0001, "latency_ms": 5, "missing_fields": ["age"],
                "checks": [], "documents": [], "transcripts": []}

    monkeypatch.setattr(multimodal, "extract", fake_extract)
    r = c.post("/profiles/extract", data={"text": "I pay 900 rent"},
               files=[("files", ("payslip.jpg", b"img", "image/jpeg")), ("files", ("note.wav", b"RIFF", "audio/wav"))])
    j = r.json()
    assert r.status_code == 200 and j["extractor"] == "fake" and j["profile"]["provenance"]["cash"]
    assert {"profile", "extractor", "cost_usd", "latency_ms", "missing_fields"} <= set(j)
    assert seen == {"files": ["payslip.jpg"], "text": "I pay 900 rent", "audio": b"RIFF", "audio_format": "wav"}


def test_extract_falls_back_to_mock_without_deps(monkeypatch):
    import multimodal

    def missing(*a, **k):
        raise ImportError("No module named 'rapidocr_onnxruntime'")

    monkeypatch.setattr(multimodal, "extract", missing)
    j = c.post("/profiles/extract", data={"text": "hi"}).json()
    assert j["extractor"] == "mock" and "mock_reason" in j and j["profile"]["provenance"]


def test_extract_needs_input():
    assert c.post("/profiles/extract", data={}).status_code == 422
