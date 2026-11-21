import os

import pytest
from fastapi.testclient import TestClient

os.environ["OPENROUTER_API_KEY"] = ""  # tests never spend money: agent uses templates
os.environ["TOGETHER_API_KEY"] = ""

from api.main import app  # noqa: E402
from api.agent import check_grounding  # noqa: E402

c = TestClient(app)


def test_health():
    assert c.get("/health").json()["ok"]


def test_expand_root():
    j = c.post("/tree/expand", json={"path": []}).json()
    ids = {n["node_id"]: n["status"] for n in j["nodes"]}
    assert ids == {"0": "chosen", "1": "child", "2": "child", "3": "child"}
    for k in ("cost_usd", "latency_ms", "model"):
        assert k in j


def test_expand_prunes_and_matches_ubs_kit():
    j = c.post("/tree/expand", json={"path": ["2", "2.1"]}).json()
    status = {n["node_id"]: n["status"] for n in j["nodes"]}
    assert status["2.1"] == "chosen" and status["2.2"] == "sibling" and status["2.1.1"] == "child"
    assert "1" not in status and "3" not in status  # pruned
    master = next(n for n in j["nodes"] if n["node_id"] == "2")["result"]
    # UBS starter kit: master's path min cash -18,600, first shortfall month 7 (index 6)
    assert master["metrics"]["min_cash"] == -18600
    assert master["metrics"]["first_negative_month"] == 6
    work = next(n for n in c.post("/tree/expand", json={"path": []}).json()["nodes"] if n["node_id"] == "1")
    assert work["result"]["deterministic"]["cash"][-1] == 152000
    for n in j["nodes"]:
        r = n["result"]
        assert all(ch["passed"] for ch in r["checks"]), (n["node_id"], r["checks"])
        assert len(r["bands"]["net_worth"]["p50"]) == 121


def test_bad_path():
    assert c.post("/tree/expand", json={"path": ["1.2"]}).status_code == 422


def test_assumption_override_and_weather():
    base = c.post("/tree/expand", json={"path": ["1"]}).json()
    up = c.post("/tree/expand", json={"path": ["1"], "assumptions": [{"id": "AS-salary-junior-ch", "value": 5000}],
                                      "weather": ["job_loss"]}).json()
    f = lambda j: next(n for n in j["nodes"] if n["node_id"] == "1")["result"]  # noqa: E731
    assert f(up)["weather"] == ["job_loss"]
    assert f(up)["deterministic"]["cash"][-1] != f(base)["deterministic"]["cash"][-1]


def test_simulate():
    j = c.post("/simulate", json={"node": {"node_id": "3"}}).json()
    assert j["result"]["node_id"] == "3"


@pytest.mark.parametrize("lang,q", [("es", "¿Qué pasa si hago el máster?"), ("en", "What happens with the master?"),
                                    ("fr", "Qu'est-ce qui se passe si je fais le master ?")])
def test_agent_template(lang, q):
    j = c.post("/agent/ask", json={"question": q, "context": {"path": ["2"]}}).json()
    assert j["mode"] == "template" and j["language"] == lang
    assert "18'600" in j["answer"] or "7" in j["answer"]
    assert j["cost_usd"] == 0


def test_grounding():
    tools = [{"final_net_worth_p50": 143660.86, "min_cash": -18600.0}]
    assert check_grounding("Median CHF 143'661, lowest CHF -18'600 in 2029.", tools)["grounded"]
    assert not check_grounding("You would have CHF 250'000.", tools)["grounded"]
