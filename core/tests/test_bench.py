"""Calibration harness (#42). Public-target scoring always runs; the UBS-data checks need
the private kit (bash scripts/fetch_ubs_kit.sh) and are skipped without it."""
import pytest

from core.bench import harness, ubs


def test_score_counts_only_verified_targets_by_default():
    s = harness.score()
    used = [p for p in s["parts"] if p["used"]]
    assert used and all(p["status"] == "verified" for p in used)
    assert s["loss"] >= 0 and s["targets_used"] == len(used)
    worse = harness.score({"AS-inflation-mean": 0.03})
    assert worse["loss"] > s["loss"]


def test_targets_are_sourced_and_statuses_known():
    for t in harness.load_targets():
        assert t["status"] in ("verified", "to_verify", "to_fill") and t["source"] and t["url"].startswith("https://")
        assert (t["target"] is None) == (t["status"] == "to_fill")


def test_grid_search_ranks_by_loss():
    res = harness.search({"AS-inflation-mean": [0.0, 0.01, 0.03]})
    assert [r["loss"] for r in res] == sorted(r["loss"] for r in res)
    assert res[0]["overrides"]["AS-inflation-mean"] == 0.01


needs_kit = pytest.mark.skipif(not ubs.available(), reason="UBS kit not fetched (bash scripts/fetch_ubs_kit.sh)")


@needs_kit
def test_ubs_ledgers_are_consistent():
    assert harness.ledger_consistency()["passed"]


@needs_kit
def test_zero_world_replay_turns_the_same_budget_into_the_same_cash():
    # smoke check only: the budget is each profile's own 24-month average, so the final cash
    # matches by construction; the path error measures only the timing of irregular items
    r = harness.replay(world="zero")
    assert abs(r["final_cash_error_months_of_budget"]["median"]) < 0.01
    assert r["mean_abs_path_error_months_of_budget"] < 0.5  # only the timing of irregular items


def test_rule_parameters_are_never_searched():
    with pytest.raises(ValueError):
        harness.search({"AS-debt-service-limit": [0.3, 0.4]})


def test_params_file_round_trips_into_score():
    ov, classes = harness.load_params(harness.HERE / "params.json")
    assert set(classes.values()) <= {"tunable", "rule"}
    assert harness.score(ov)["loss"] == harness.score()["loss"]  # the file holds today's defaults


@needs_kit
def test_ubs_scenario_assumptions_are_compared_with_the_tree():
    rows = {r["parameter"]: r for r in harness.scenario_assumptions_vs_tree()}
    assert rows["annual_tuition_chf"]["ubs_alexia"] == 8000.0
    assert rows["annual_tuition_chf"]["ours_range"][1] == 8000  # the UBS figure is our high end


@needs_kit
def test_ubs_profiles_are_replayed_as_take_home():
    take = harness.replay(world="swiss")
    before = harness.replay(world="swiss", income_basis="net_before_tax")
    assert take["income_basis"] == "take_home"
    # without the second income tax the Swiss world stays within half a month of budget of their ledgers
    assert abs(take["final_cash_error_months_of_budget"]["median"]) < 0.5
    assert before["final_cash_error_months_of_budget"]["median"] < -2
