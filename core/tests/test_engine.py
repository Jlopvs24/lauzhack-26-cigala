"""Validation of the financial engine: identities, edge cases, reproducibility,
UBS starter-kit reproduction, lazy tree and weather.

    python -m pytest core/tests -q
"""
import json
import time
from pathlib import Path

import pytest

from core import expand, load_profile, load_tree, simulate, simulate_node, visible_nodes
from core.tree import pruned_nodes
from core.assumptions import build_assumptions, zero_world_assumptions
from core.starter import simulate_starter

ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT / "vendor" / "ubs-kit" / "starter-kit"

ZERO = build_assumptions(base=zero_world_assumptions())


def base_profile(**kw):
    p = {"profile_id": "T", "as_of": "2025-01-01", "horizon_months": 24, "cash": 8000,
         "monthly_net_income": 1200, "monthly_rent": 0, "monthly_other_expenses": 1800}
    p.update(kw)
    return p


def all_passed(res):
    return {c["name"]: c["passed"] for c in res["checks"]}


# --- UBS starter kit ---------------------------------------------------------

STARTER_SCENARIOS = {
    "Start working": {"phases": [{"start_month": 0, "end_month": 120, "monthly_income_chf": 4200, "monthly_expenses_chf": 3000}], "one_off_costs": []},
    "Master's degree": {"phases": [{"start_month": 0, "end_month": 24, "monthly_income_chf": 1200, "monthly_expenses_chf": 2100},
                                   {"start_month": 24, "end_month": 120, "monthly_income_chf": 4800, "monthly_expenses_chf": 3100}],
                        "one_off_costs": [{"month": 0, "amount_chf": 2500}, {"month": 12, "amount_chf": 2500}]},
    "Move abroad": {"phases": [{"start_month": 0, "end_month": 120, "monthly_income_chf": 3700, "monthly_expenses_chf": 2900}],
                    "one_off_costs": [{"month": 0, "amount_chf": 6500}]},
}
STARTER_PROFILE = {"name": "Alexia", "opening_cash_chf": 8000, "horizon_months": 120}


@pytest.mark.parametrize("name,closing,minimum,first_neg", [
    ("Start working", 152000.0, 9200.0, None),      # starter's min 8000 includes the opening balance
    ("Master's degree", 144600.0, -18600.0, 6),     # starter prints "Month 7" (1-based)
    ("Move abroad", 97500.0, 2300.0, None),
])
def test_reproduces_ubs_starter_kit(name, closing, minimum, first_neg):
    res = simulate_starter(STARTER_PROFILE, {"name": name, **STARTER_SCENARIOS[name]})
    m = res["metrics"]
    assert m["final_cash"] == closing
    assert m["min_cash"] == minimum
    assert m["first_negative_month"] == first_neg
    assert all(all_passed(res).values())


@pytest.mark.skipif(not STARTER.exists(), reason="UBS kit not fetched (bash scripts/fetch_ubs_kit.sh)")
def test_matches_starter_kit_code_month_by_month():
    import sys
    sys.path.insert(0, str(STARTER))
    from financial_twin import simulate as ubs_simulate  # noqa: E402
    profile = json.loads((STARTER / "sample_profile.json").read_text(encoding="utf-8"))
    for sc in json.loads((STARTER / "scenario_config.json").read_text(encoding="utf-8"))["scenarios"]:
        ours = simulate_starter(profile, sc)["deterministic"]["cash"][1:]
        theirs = list(ubs_simulate(profile, sc).cash_by_month_chf)
        assert ours == pytest.approx(theirs, abs=0.01)


# --- accounting identities ---------------------------------------------------

def test_validation_guide_example():
    # UBS technical-validation.md: 8000 + 1200 - 1800 = 7400
    res = simulate_node(base_profile(horizon_months=1), [], assumptions=ZERO, n_paths=10)
    assert res["deterministic"]["cash"] == [8000.0, 7400.0]


def test_identities_hold_in_rich_scenario():
    prof = base_profile(horizon_months=120, monthly_investment_contribution=300, monthly_net_income=5000,
                        assets=[{"type": "investment", "value": 10000}],
                        liabilities=[{"type": "loan", "principal": 20000, "annual_rate": 0.05, "monthly_payment": 400}])
    ivs = [{"param": "new_liability", "month": 10, "liability": {"principal": 5000, "annual_rate": 0.03, "monthly_payment": 100}},
           {"param": "one_off_cost", "month": 30, "value": 25000}]
    res = simulate_node(prof, ivs, weather=["recession", "market_crash"], n_paths=200)
    assert all(all_passed(res).values()), res["checks"]


def test_transfer_to_investments_does_not_reduce_net_worth():
    prof = base_profile(horizon_months=1, monthly_net_income=0, monthly_other_expenses=0,
                        monthly_investment_contribution=500)
    res = simulate_node(prof, [], assumptions=ZERO, n_paths=10)
    d = res["deterministic"]
    assert d["cash"][1] == 7500.0 and d["investments"][1] == 500.0
    assert d["net_worth"][1] == 8000.0


def test_principal_repayment_reduces_cash_and_debt_interest_is_expense():
    prof = base_profile(horizon_months=1, monthly_net_income=0, monthly_other_expenses=0,
                        liabilities=[{"principal": 12000, "annual_rate": 0.12, "monthly_payment": 1120}])
    d = simulate_node(prof, [], assumptions=ZERO, n_paths=10)["deterministic"]
    assert d["cash"][1] == pytest.approx(8000 - 1120)
    assert d["debt"][1] == pytest.approx(12000 + 120 - 1120)
    assert d["net_worth"][1] - d["net_worth"][0] == pytest.approx(-120)  # only interest destroys wealth


# --- edge cases --------------------------------------------------------------

def test_zero_income_flags_negative_cash():
    res = simulate_node(base_profile(cash=0, monthly_net_income=0), [], assumptions=ZERO, n_paths=10)
    assert res["metrics"]["first_negative_month"] == 0
    assert res["metrics"]["shortfall_probability"] == 1.0


def test_zero_interest_loan_no_division_error():
    prof = base_profile(liabilities=[{"principal": 2400, "annual_rate": 0.0, "monthly_payment": 100}])
    res = simulate_node(prof, [], assumptions=ZERO, n_paths=10)
    assert res["debts"][0]["paid_off_month"] == 23
    assert res["metrics"]["final_debt"] == 0.0


def test_loan_paid_off_never_goes_negative():
    prof = base_profile(liabilities=[{"principal": 500, "annual_rate": 0.05, "monthly_payment": 300}])
    res = simulate_node(prof, [], n_paths=10)
    assert min(res["deterministic"]["debt"]) >= 0
    assert all_passed(res)["debt_never_negative"]


def test_negative_return_reduces_portfolio():
    prof = base_profile(monthly_net_income=1800, assets=[{"type": "investment", "value": 10000}])
    res = simulate_node(prof, [], overrides={"investment_return_mean": -0.10}, n_paths=10)
    inv = res["deterministic"]["investments"]
    assert inv[-1] < inv[0]


def test_higher_tuition_never_helps():
    tree = load_tree()
    lo = simulate(None, "2", {"AS-alexia-master-tuition": 1460}, n_paths=200, sensitivity=False)
    hi = simulate(None, "2", {"AS-alexia-master-tuition": 8000}, n_paths=200, sensitivity=False)
    assert hi["metrics"]["final_net_worth"] < lo["metrics"]["final_net_worth"]
    assert hi["metrics"]["min_cash"] < lo["metrics"]["min_cash"]
    assert tree["tree_id"]


def test_scenario_isolation_unrelated_assumption_has_no_effect():
    a = simulate(None, "1", None, n_paths=200, sensitivity=False)
    b = simulate(None, "1", {"AS-alexia-move-cost": 9000}, n_paths=200, sensitivity=False)
    assert a["metrics"] == b["metrics"]


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        simulate_node(base_profile(cash="lots"), [])
    with pytest.raises(ValueError):
        simulate_node(base_profile(), [{"param": "one_off_cost", "month": 999, "value": 1}])
    with pytest.raises(ValueError):
        simulate_node(base_profile(), [{"param": "one_off_cost", "month": 1, "value": -5}])
    with pytest.raises(ValueError):
        simulate_node(base_profile(), [{"param": "salary", "value": 1}])
    with pytest.raises(ValueError):
        simulate_node(base_profile(), [], weather=["meteor"])
    with pytest.raises(ValueError):
        simulate_node(base_profile(), [], overrides={"AS-does-not-exist": 1})


# --- reproducibility and Monte Carlo -----------------------------------------

def test_same_seed_same_result_different_seed_different_bands():
    a = simulate(None, "3", n_paths=300, seed=7, sensitivity=False)
    b = simulate(None, "3", n_paths=300, seed=7, sensitivity=False)
    c = simulate(None, "3", n_paths=300, seed=8, sensitivity=False)
    strip = lambda r: {k: v for k, v in r.items() if k != "timing_ms"}  # noqa: E731
    assert strip(a) == strip(b)
    assert a["bands"] != c["bands"]
    assert a["deterministic"] == c["deterministic"]


def test_bands_ordered_and_contain_reasonable_spread():
    r = simulate(None, "1.1", sensitivity=False)
    nw = r["bands"]["net_worth"]
    assert nw["p10"][-1] < nw["p50"][-1] < nw["p90"][-1]
    assert len(nw["p50"]) == 121 and len(r["deterministic"]["flows"]["income"]) == 120


def test_monte_carlo_under_200ms_per_node():
    simulate(None, "2", sensitivity=False)  # warm-up
    best = float("inf")
    for _ in range(3):  # best of 3: robust to a busy machine
        t = time.perf_counter()
        simulate(None, "2", sensitivity=False)
        best = min(best, time.perf_counter() - t)
    assert best < 0.2


# --- lazy tree ---------------------------------------------------------------

def test_visible_nodes_prune_far_branches():
    tree = load_tree()
    ids = lambda path: {str(n["node_id"]): s for n, s, _ in visible_nodes(tree, path)}  # noqa: E731
    assert set(ids([])) == {"0", "1", "2", "3"}
    v = ids(["2", "2.1"])
    assert set(v) == {"0", "2", "2.1", "2.2", "2.3"}       # 1 and 3 are pruned
    assert v["2.2"] == "sibling"
    v = ids(["2"])
    assert v["1"] == "sibling" and v["2.1"] == "child"


def test_expand_envelope_and_back():
    r = expand(load_profile(), ["2", "2.2"], [{"id": "AS-alexia-master-tuition", "value": 3000}], ["job_loss"])
    assert r["current"] == "2.2" and r["path"] == ["0", "2", "2.2"] and r["back_path"] == ["2"]
    statuses = {n["node_id"]: n["status"] for n in r["nodes"]}
    assert statuses == {"0": "chosen", "2": "chosen", "2.2": "chosen", "2.1": "sibling", "2.3": "sibling"}
    cur = [n for n in r["nodes"] if n["is_current"]][0]
    assert cur["result"]["sensitivity"] and cur["changes"]
    assert all(all(c["passed"] for c in n["result"]["checks"]) for n in r["nodes"])
    with pytest.raises(ValueError):
        expand(load_profile(), ["2", "1.1"])


def test_child_interventions_refine_parent():
    parent = simulate(None, "2", n_paths=100, sensitivity=False)
    part_time = simulate(None, "2.3", n_paths=100, sensitivity=False)
    assert part_time["metrics"]["min_cash"] > parent["metrics"]["min_cash"]


# --- weather -----------------------------------------------------------------

@pytest.mark.parametrize("w", ["recession", "inflation", "market_crash", "job_loss"])
def test_weather_never_improves_outcome(w):
    base = simulate(None, "1.1", n_paths=300, sensitivity=False)
    stressed = simulate(None, "1.1", None, [w], n_paths=300, sensitivity=False)
    assert stressed["metrics"]["final_net_worth_real"] <= base["metrics"]["final_net_worth_real"]
    assert stressed["weather"][0]["type"] == w


def test_sensitivity_sorted_and_relevant():
    r = simulate(None, "2", n_paths=200)
    sens = r["sensitivity"]
    swings = [s["delta_final_net_worth"] for s in sens]
    assert swings == sorted(swings, reverse=True)
    assert "AS-alexia-abroad-salary" not in {s["assumption_id"] for s in sens}
    assert sens[0]["assumption_id"] == "AS-alexia-master-salary"


def test_batched_run_matches_single_runs():
    """Each block of a batch equals the same scenario run alone (common random numbers)."""
    from core.assumptions import build_assumptions
    from core.engine import run, run_batch
    from core.models import Profile, parse_interventions
    from core.schedule import build_schedule
    from core.tree import flatten_interventions
    from core.weather import build_weather
    tree = load_tree()
    prof = Profile.from_dict(load_profile())
    w = build_weather(["recession"], prof.horizon_months)
    scheds, As = [], []
    for nid, ov in (("2", {}), ("2.2", {"AS-inflation-mean": 0.03}), ("1.3", {"AS-income-tax": 1.2})):
        aset = build_assumptions(tree["assumptions"], ov)
        A = aset.values()
        scheds.append(build_schedule(prof, parse_interventions(flatten_interventions(tree, nid), A, prof.horizon_months)))
        As.append(A)
    batch = run_batch(scheds, As, prof.cash, prof.investments, aset.tax_table(), w, n_paths=50, seed=3, stochastic=True)
    for k in range(3):
        single = run(scheds[k], prof.cash, prof.investments, As[k], aset.tax_table(), w, n_paths=50, seed=3, stochastic=True)
        assert batch.net_worth[k * 50:(k + 1) * 50] == pytest.approx(single.net_worth)
        assert batch.cash[k * 50:(k + 1) * 50] == pytest.approx(single.cash)


def test_tornado_fast():
    simulate(None, "2")  # warm-up
    best = float("inf")
    for _ in range(3):
        t = time.perf_counter()
        simulate(None, "2", sensitivity=True)
        best = min(best, time.perf_counter() - t)
    assert best < 0.4  # node (~0.05-0.09 s) + tornado (~0.1 s), with margin for a busy machine


# --- pruned ghost nodes ------------------------------------------------------

def _three_level_tree():
    def node(nid, children=()):
        return {"node_id": nid, "label": f"Option {nid}", "interventions": [], "children": list(children)}
    level3 = lambda p: [node(f"{p}.{i}") for i in (1, 2, 3)]  # noqa: E731
    level2 = lambda p: [node(f"{p}.{i}", level3(f"{p}.{i}")) for i in (1, 2, 3)]  # noqa: E731
    return {"tree_id": "t3", "assumptions": [], "root": node("0", [node(str(i), level2(str(i))) for i in (1, 2, 3)])}


@pytest.mark.parametrize("path,expected", [
    ([], set()),
    (["2"], set()),                                    # depth 1: the root has no siblings
    (["2", "2.1"], {"1", "3"}),                        # depth 2: siblings of "2"
    (["2", "2.1", "2.1.3"], {"1", "3", "2.2", "2.3"}),  # depth 3: siblings of "2" and of "2.1"
])
def test_pruned_nodes_set(path, expected):
    tree = _three_level_tree()
    ghosts = pruned_nodes(tree, path)
    assert {g["node_id"] for g in ghosts} == expected
    visible = {str(n["node_id"]) for n, _, _ in visible_nodes(tree, path)}
    assert not visible & expected                      # a node is either visible or a ghost, never both
    for g in ghosts:
        assert g["status"] == "pruned" and "result" not in g
        assert set(g) == {"node_id", "parent_id", "label", "status", "depth", "has_children"}
        assert g["depth"] == g["node_id"].count(".") + 1
        assert g["has_children"] == (g["depth"] < 3)


def test_pruned_nodes_never_simulated(monkeypatch):
    import core.tree as ct
    simulated = []
    real = ct.simulate_node
    monkeypatch.setattr(ct, "simulate_node", lambda prof, ivs, **kw: simulated.append(kw["node_id"]) or real(prof, ivs, **kw))
    ct._CACHE.clear()
    r = ct.expand(load_profile(), ["2", "2.1", "2.1.3"], tree=_three_level_tree(), n_paths=50, sensitivity=False)
    ghosts = {g["node_id"] for g in r["pruned_nodes"]}
    assert ghosts == {"1", "3", "2.2", "2.3"}
    assert not ghosts & set(simulated)
    assert set(simulated) == {n["node_id"] for n in r["nodes"]} == {"0", "2", "2.1", "2.1.3", "2.1.1", "2.1.2"}
    assert all(n["status"] != "pruned" for n in r["nodes"])  # ghosts live only in pruned_nodes


def test_expand_on_real_tree_returns_ghosts():
    r = expand(load_profile(), ["1", "1.2"])
    assert [g["node_id"] for g in r["pruned_nodes"]] == ["2", "3"]
    assert expand(load_profile(), ["1"])["pruned_nodes"] == []
