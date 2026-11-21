"""Profile-aware tree (#77): another profile re-bases the person-specific amounts and gets its own
root narration; the reference profile (Alexia) is untouched, to the cent."""
import pytest

import core
from core.tree import for_profile, load_profile, load_tree

FAST = dict(sensitivity=False, exploration=False)
# (final_net_worth, min_cash) of every node for Alexia on master b00380f, before #77
ALEXIA = {
    "0": (-22055.8, -22055.8), "1": (125604.88, 8736.47), "1.1": (125604.88, 8736.47), "1.1.1": (143606.67, 8871.59),
    "1.1.2": (171509.7, 8736.47), "1.1.3": (47079.63, 8147.1), "1.2": (139075.54, 8236.47),
    "1.2.1": (139075.54, 8236.47), "1.2.2": (136732.08, 8236.47), "1.2.3": (145088.34, 8236.47),
    "1.3": (76006.64, 8486.47), "1.3.1": (77537.21, 6759.53), "1.3.2": (111861.02, 8486.47),
    "1.3.3": (85915.89, 8887.96), "2": (113329.61, -18553.21), "2.1": (113329.61, -18553.21),
    "2.1.1": (131589.85, -425.33), "2.1.2": (85913.45, -31808.99), "2.1.3": (123220.29, -8731.34),
    "2.2": (113364.98, -3537.61), "2.2.1": (113364.98, -3537.61), "2.2.2": (113349.6, -3537.61),
    "2.2.3": (111503.03, -3537.61), "2.3": (129802.42, 5775.55), "2.3.1": (137445.44, 8275.55),
    "2.3.2": (154900.83, 6447.1), "2.3.3": (117401.25, 5775.55), "3": (53065.08, 1746.18),
    "3.1": (53065.08, 1746.18), "3.1.1": (62731.76, 0.0), "3.1.2": (104295.64, 1746.18),
    "3.1.3": (50539.95, -754.17), "3.2": (116419.48, 2246.07), "3.2.1": (116419.48, 2246.07),
    "3.2.2": (92439.18, 1515.46), "3.2.3": (156034.17, 2246.07), "3.3": (136036.29, 1746.18),
    "3.3.1": (136036.29, 1746.18), "3.3.2": (96319.16, -17377.48), "3.3.3": (149398.34, 1746.18),
}
SAM = dict(load_profile(), profile_id="U1", display_name="Sam", employment_status="apprentice", city="Geneva",
           cash=3000, monthly_net_income=2000, monthly_rent=1300, monthly_other_expenses=900)


def _nodes(r):
    return {n["node_id"]: n for n in r["nodes"]}


def test_alexia_is_unchanged_on_every_node():
    tree = load_tree()
    assert for_profile(tree, load_profile()) is tree  # the reference profile gets the tree file as is
    assert set(ALEXIA) == set(core.tree._index(tree))
    for nid, (final, low) in ALEXIA.items():
        m = core.simulate(None, nid, **FAST)["metrics"]
        assert (m["final_net_worth"], m["min_cash"]) == (final, low), nid
    r = core.expand(load_profile(), [], **FAST)  # the API passes the profile explicitly
    root = _nodes(r)["0"]
    assert root["label"] == "Today: student in Lausanne" and root["description"].startswith("Alexia keeps")
    assert not root["generated_from_profile"] and r["profile_basis"]["is_reference"] is True


def test_another_profile_gets_its_own_root_narration():
    r = core.expand(SAM, [], **FAST)
    root = _nodes(r)["0"]
    assert root["label"] == "Today: apprentice in Geneva" and root["generated_from_profile"]
    assert "Sam" in root["description"] and "Alexia" not in root["description"]
    assert "CHF 2,000" in root["description"] and "CHF 2,200" in root["description"] and "CHF 3,000" in root["description"]
    basis = r["profile_basis"]
    assert basis["is_reference"] is False and basis["reference_profile_id"] == "P00001"
    assert basis["deltas_vs_reference"] == {"monthly_net_income": 800.0, "monthly_rent": 400.0, "monthly_other_expenses": 300.0}
    anon = _nodes(core.expand(dict(SAM, display_name="", city=None, employment_status=None), [], **FAST))["0"]
    assert anon["label"] == "Today: your current life" and anon["description"].startswith("You keep your current life")


def test_person_specific_amounts_follow_the_profile_and_market_figures_do_not():
    r = core.expand(SAM, ["2"], **FAST)
    n = _nodes(r)
    ivs = {iv["label"]: iv for iv in n["2"]["interventions"]}
    assert ivs["Student room"]["value"] == 1300 and ivs["Student room"]["reference_value"] == 900  # own rent
    assert ivs["Student living costs"]["value"] == 1500  # own CHF 900 + the CHF 600 the tree adds while studying
    assert ivs["Living costs as a worker"]["value"] == 2300  # own level + CHF 1,400
    A = {a["id"]: a for a in r["assumptions"]}
    job = A["AS-alexia-student-job"]  # the income kept while studying is the person's own
    assert (job["value"], job["reference_value"], job["range"], job["profile_adjusted"]) == (2000, 1200, [1400, 2400], True)
    for market in ("AS-alexia-master-salary", "AS-alexia-work-salary", "AS-alexia-work-rent", "AS-alexia-master-tuition"):
        assert "profile_adjusted" not in A[market] and A[market]["value"] == {a["id"]: a for a in load_tree()["assumptions"]}[market]["value"]
    assert any("net income = CHF 2,000/month" in c for c in n["2"]["changes"])
    # the branch numbers move with the profile, like-for-like with a direct simulate
    assert n["2"]["result"]["metrics"]["final_net_worth"] != ALEXIA["2"][0]
    assert core.simulate(SAM, "2", **FAST)["metrics"] == n["2"]["result"]["metrics"]
    # a user override of the adjusted assumption still wins
    over = core.simulate(SAM, "2", {"AS-alexia-student-job": 1500}, **FAST)
    assert over["metrics"]["final_net_worth"] < n["2"]["result"]["metrics"]["final_net_worth"]


def test_euro_amounts_convert_the_difference_and_floors_hold():
    abroad = {iv["label"]: iv for iv in _nodes(core.expand(SAM, ["3"], **FAST))["3"]["interventions"]}
    fx = core.build_assumptions().values()["eurchf"]
    assert abroad["Living costs abroad"]["value"] == pytest.approx(1843 + 300 / fx, abs=0.01)
    frugal = dict(SAM, monthly_other_expenses=0, monthly_rent=0)
    ivs = {iv["label"]: iv for iv in _nodes(core.expand(frugal, ["2"], **FAST))["2"]["interventions"]}
    assert ivs["Student room"]["value"] == 0 and ivs["Student living costs"]["value"] == 600


def test_every_entry_point_uses_the_profile_tree():
    ref = core.simulate(SAM, "2.1", **FAST)["metrics"]["final_net_worth"]
    rep = core.report_data(SAM, ["2", "2.1"])
    assert rep["steps"][1]["result"]["metrics"]["final_net_worth"] == ref
    assert rep["baseline"]["label"] == "Today: apprentice in Geneva"
    assert core.explore(SAM, ["2", "2.1"])["node_id"] == "2.1"
    combo = core.combine(SAM, "1.2", "1.3")
    assert combo["result"]["metrics"]["final_net_worth"] != core.combine(None, "1.2", "1.3")["result"]["metrics"]["final_net_worth"]
    gross = dict(SAM, monthly_net_income=0, monthly_gross_income=3000, age=22)  # a gross salary counts as its net
    assert core.expand(gross, [], **FAST)["profile_basis"]["baseline"]["monthly_net_income"] == pytest.approx(
        core.payslip(3000, 22)["net"], abs=0.01)
