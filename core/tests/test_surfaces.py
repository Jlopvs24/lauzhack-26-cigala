"""Combined decisions, 2-lever surfaces, constraint-targeted search, timing scan (#48 item 6)."""
import pytest

import core
from core import tree as tr
from core.assumptions import build_assumptions

P = core.load_profile()
T = core.load_tree()
ASET = build_assumptions(T.get("assumptions", []))


def direct(ivs, overrides=None):
    aset = ASET.with_overrides(overrides) if overrides else ASET
    return core.simulate_node(P, ivs, assumptions=aset, sensitivity=False, exploration=False)


def test_plan_level_matches_plan_check_on_the_tree():
    from core import plan as pl
    for nid in ("0", "1", "2", "3", "3.3.2"):
        r = core.simulate(P, nid)
        assert pl.plan_level(r["constraints"]) == r["plan_check"]["level"], nid


def test_surface_cells_equal_direct_simulation():
    x = {"assumption": "AS-alexia-master-tuition"}
    y = {"param": "monthly_net_income", "op": "add", "range": [0, 1200], "label": "Extra income"}
    s = core.surface(P, ["0", "2"], x, y, n=3, compare_to="1")
    assert len(s["cells"]) == 3 and len(s["cells"][0]) == 3 and s["x"]["values"][0] == ASET.get("AS-alexia-master-tuition")["range"][0]
    ivs = tr.flatten_interventions(T, "2")
    for i, j in ((0, 0), (2, 1), (1, 2)):
        c = s["cells"][i][j]
        extra = [{"param": "monthly_net_income", "op": "add", "value": c["y"], "from_month": 0, "label": "Extra income"}]
        r = direct(ivs + extra, {"AS-alexia-master-tuition": c["x"]})
        assert c["final_net_worth"] == pytest.approx(r["metrics"]["final_net_worth"], abs=0.02)
        assert c["level"] == r["plan_check"]["level"]
        peer = direct(tr.flatten_interventions(T, "1"), {"AS-alexia-master-tuition": c["x"]})
        assert c["delta_vs_peer"] == pytest.approx(r["metrics"]["final_net_worth"] - peer["metrics"]["final_net_worth"], abs=0.05)
    # more income never makes a cell worse (monotone along y)
    for j in range(3):
        col = [s["cells"][i][j]["final_net_worth"] for i in range(3)]
        assert col == sorted(col)


def test_surface_two_assumptions_and_errors():
    s = core.surface(P, ["0", "1"], {"assumption": "AS-real-wage-growth"}, {"assumption": "AS-inflation-mean"}, n=4)
    assert s["holds_share"] >= 0 and len(s["cells"]) == 4
    with pytest.raises(ValueError, match="different"):
        core.surface(P, ["0", "1"], {"assumption": "AS-inflation-mean"}, {"assumption": "AS-inflation-mean"})
    with pytest.raises(ValueError, match="unknown assumption"):
        core.surface(P, ["0", "1"], {"assumption": "AS-nope"}, {"assumption": "AS-inflation-mean"})
    with pytest.raises(ValueError, match="n must"):
        core.surface(P, ["0", "1"], {"assumption": "AS-real-wage-growth"}, {"assumption": "AS-inflation-mean"}, n=40)


def test_smallest_change_removes_the_funding_gap_and_is_tight():
    sc = core.smallest_change(P, ["0", "2"])
    assert sc["now"]["level"] == "needs_financing" and not sc["already_holds"]
    ivs = tr.flatten_interventions(T, "2")
    for ch in sc["changes"]:
        assert ch["status"] == "threshold_found", ch
        v = ch["value"]
        if ch["param"] == "one_off_income":
            mk = lambda x: ivs + [{"param": "one_off_income", "month": 0, "value": x, "label": "lever"}]
        else:
            sign = 1 if ch["direction"] == "increase" else -1
            mk = lambda x, p=ch["param"], sign=sign: ivs + [{"param": p, "op": "add", "value": sign * x, "from_month": 0, "label": "lever"}]
        assert direct(mk(v))["metrics"]["min_cash"] >= -0.01
        assert direct(mk(max(v - 0.05, 0)))["metrics"]["min_cash"] < -0.01  # tight to the cent
        assert ch["result"]["first_negative_month"] is None


def test_smallest_change_when_it_already_holds_and_feasible_target():
    sc = core.smallest_change(P, ["0", "1"])
    assert sc["already_holds"] and all(c["status"] == "already_satisfied" for c in sc["changes"] if c["status"] != "lever_has_no_room")
    f = core.smallest_change(P, ["0", "2"], target="feasible", levers=[
        {"name": "more_income", "param": "monthly_net_income", "sign": 1, "high": 5000}])
    assert f["changes"][0]["status"] in ("threshold_found", "not_reached_within_bounds")
    with pytest.raises(ValueError, match="target"):
        core.smallest_change(P, ["0", "2"], target="rich")


def test_timing_scan():
    ts = core.timing_scan(P, ["0", "3", "3.3"])
    assert ts["status"] == "evaluated" and [r["delay_months"] for r in ts["rows"]] == [0, 6, 12, 18, 24, 30, 36]
    now = core.simulate(P, "3.3")
    assert ts["rows"][0]["final_net_worth"] == pytest.approx(now["metrics"]["final_net_worth"], abs=0.02)
    assert ts["rows"][0]["level"] == now["plan_check"]["level"]
    assert core.timing_scan(P, [])["status"] == "no_own_decision"


def test_combine_paths():
    cb = core.combine(P, "3.2", "3.3")
    assert cb["common_ancestor"] == "3" and cb["node_id"] == "3.2+3.3"
    ivs = tr.flatten_interventions(T, "3.2") + tr.lineage(T, "3.3")[-1]["interventions"]
    assert cb["result"]["metrics"]["final_net_worth"] == pytest.approx(direct(ivs)["metrics"]["final_net_worth"], abs=0.02)
    params = {c["param"] for c in cb["conflicts"]}
    assert {"monthly_net_income", "monthly_rent", "tax_residence"} <= params
    assert all(c["rule"].startswith("later wins") for c in cb["conflicts"])
    assert set(cb["compare"]) == {"combined", "a", "b"}
    with pytest.raises(ValueError, match="ancestor"):
        core.combine(P, "3", "3.3")
    with pytest.raises(ValueError, match="nothing to combine"):
        core.combine(P, "3.3", "3")
    # combining across top-level branches works too
    assert core.combine(P, "1", "2")["common_ancestor"] == "0"


def test_custom_nodes_flow_through():
    cn = [{"parent_id": "2", "node_id": "2.c1", "label": "Master + scholarship",
           "interventions": [{"param": "one_off_income", "month": 0, "value": 7200, "label": "Scholarship"}]}]
    sc = core.smallest_change(P, ["0", "2", "2.c1"], custom_nodes=cn)
    base = core.smallest_change(P, ["0", "2"])
    cash = lambda r: next(c for c in r["changes"] if c["lever"] == "cash_now")["value"]
    assert cash(sc) == pytest.approx(cash(base) - 7200, abs=60)  # roughly 7,200 less needed (interest)
