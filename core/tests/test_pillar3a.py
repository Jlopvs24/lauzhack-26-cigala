"""Pillar 3a lever (#48 item 4): capped, tax-deductible, locked (in net worth, not liquid)."""
import numpy as np
import pytest

import core
from core.models import Profile

BASE = {"as_of": "2026-01-01", "horizon_months": 36, "cash": 20000, "monthly_net_income": 6000,
        "monthly_rent": 1800, "monthly_other_expenses": 1500, "city": "Lausanne"}


def by_year(flow, start_month=1):
    a = np.asarray(flow)
    years = (start_month - 1 + np.arange(len(a))) // 12
    return [round(float(a[years == y].sum()), 2) for y in np.unique(years)]


def test_2026_caps_are_verified():
    recs = {a["param"]: a for a in core.default_assumptions()}
    assert recs["pillar3a_max"]["value"] == 7258 and recs["pillar3a_max"]["verified"]
    assert recs["pillar3a_max_no_bvg"]["value"] == 36288 and recs["pillar3a_no_bvg_share"]["value"] == 0.2
    assert recs["pillar3a_max"]["value"] == round(0.08 * recs["payroll_bvg_max"]["value"])  # Art. 7 BVV 3
    assert recs["pillar3a_return"]["verified"] is True and recs["pillar3a_return"]["range"]  # Moneyland average


def test_payments_are_capped_per_calendar_year_and_reset_in_january():
    r = core.simulate_node({**BASE, "as_of": "2026-07-01", "monthly_pillar_3a": 1000})
    years = by_year(r["deterministic"]["flows"]["pillar_3a_contribution"], start_month=7)
    assert years[0] == pytest.approx(6000, rel=0.01)  # Jul-Dec 2026: 6 x 1000 (indexed), under the cap
    assert years[1] == pytest.approx(7258, abs=0.05) and years[2] == pytest.approx(7258, abs=0.05)  # capped (flows in cents)
    assert r["metrics"]["total_pillar_3a_contributions"] == pytest.approx(sum(years))


def test_without_pension_fund_the_cap_is_20_percent_of_earned_income():
    r = core.simulate_node({**BASE, "monthly_net_income": 1200, "monthly_rent": 500, "monthly_other_expenses": 300,
                            "monthly_pillar_3a": 500})  # CHF 14,400/year: under the BVG entry threshold
    years = by_year(r["deterministic"]["flows"]["pillar_3a_contribution"])
    assert years[0] == pytest.approx(0.2 * 14400)


def test_tax_saving_equals_the_tax_difference_and_identities_hold():
    plain = core.simulate_node(BASE)
    p3 = core.simulate_node({**BASE, "monthly_pillar_3a": 605})
    m = p3["metrics"]
    assert m["total_pillar_3a_tax_saving"] > 0
    assert plain["metrics"]["total_income_tax"] - m["total_income_tax"] == pytest.approx(m["total_pillar_3a_tax_saving"], abs=0.05)
    assert all(c["passed"] for c in p3["checks"]), p3["checks"]
    assert any(c["name"] == "pillar_3a_account_identity" for c in p3["checks"])
    # locked: in net worth, not in cash/investments/liquidity
    assert m["final_pillar_3a"] > m["total_pillar_3a_contributions"]  # plus its return
    final_nw = p3["deterministic"]["cash"][-1] + p3["deterministic"]["investments"][-1] + p3["deterministic"]["pillar_3a"][-1]
    assert m["final_net_worth"] == pytest.approx(final_nw, abs=0.05)
    assert m["liquidity_months"] <= plain["metrics"]["liquidity_months"]


def test_paid_only_when_cash_allows_and_never_creates_a_gap():
    tight = {**BASE, "cash": 0, "monthly_net_income": 4000, "monthly_rent": 1800, "monthly_other_expenses": 1500,
             "monthly_pillar_3a": 605}  # about CHF 400/month left after tax: less than the planned 605
    r = core.simulate_node(tight)
    plain = core.simulate_node({**tight, "monthly_pillar_3a": 0})
    assert min(r["deterministic"]["cash"]) >= -0.01 and min(plain["deterministic"]["cash"]) >= -0.01
    assert r["metrics"]["total_pillar_3a_contributions"] < 605 * 36  # partly paid


def test_goals_liquid_vs_net_worth():
    g = {"name": "G", "target": 60000, "target_date": "2028-12-01"}
    liquid = core.simulate_node({**BASE, "monthly_pillar_3a": 605, "goals": [g]})
    nw = core.simulate_node({**BASE, "monthly_pillar_3a": 605, "goals": [{**g, "metric": "net_worth"}]})
    assert nw["goals"][0]["deterministic_value"] - liquid["goals"][0]["deterministic_value"] == pytest.approx(
        nw["deterministic"]["pillar_3a"][36], abs=0.05)


def test_opening_3a_assets_are_locked_not_investments():
    p = Profile.from_dict({**BASE, "assets": [{"type": "pension_3a", "value": 10000}, {"type": "investment", "value": 5000}]})
    assert p.pillar_3a == 10000 and p.investments == 5000
    r = core.simulate_node({**BASE, "assets": [{"type": "pension_3a", "value": 10000}]})
    assert r["deterministic"]["pillar_3a"][0] == 10000 and r["deterministic"]["investments"][0] == 0


def test_intervention_and_batched_paths():
    ivs = [{"param": "monthly_pillar_3a", "op": "set", "value": 605, "from_month": 6}]
    r = core.simulate_node(BASE, ivs, own_interventions=ivs, exploration=True, uncertainty=True,
                           sensitivity=True, n_paths=200)
    assert all(c["passed"] for c in r["checks"]), r["checks"]
    assert r["deterministic"]["flows"]["pillar_3a_contribution"][5] == 0 and r["deterministic"]["flows"]["pillar_3a_contribution"][6] > 0
    e = r["exploration"]["pillar_3a"]
    assert e["status"] == "evaluated" and e["monthly_amount"] == pytest.approx(7258 / 12, abs=0.01)
    opts = {o["option"]: o for o in e["options"]}
    assert opts["keep_in_cash"]["paid_into_3a"] == 0 and opts["pay_into_3a"]["tax_saved_by_3a"] > 0
    assert opts["invest"]["invested"] > 0 and opts["invest"]["paid_into_3a"] == 0
    assert opts["pay_into_3a"]["final_liquid"] < opts["keep_in_cash"]["final_liquid"]


def test_goal_seek_on_the_contribution():
    goal = {"name": "Buffer", "target": 45000, "target_date": "2028-12-01"}
    e = core.simulate_node({**BASE, "goals": [goal]}, exploration=True)["exploration"]["pillar_3a"]
    seek = e["max_monthly_3a_keeping_goals"]
    assert seek["status"] in ("found", "full_amount_keeps_goals", "goals_already_missed")
    if seek["status"] == "found":
        ok = core.simulate_node({**BASE, "goals": [goal], "monthly_pillar_3a": seek["value"]})
        assert ok["goals"][0]["met_deterministic"]
        bad = core.simulate_node({**BASE, "goals": [goal], "monthly_pillar_3a": seek["value"] + 1})
        assert not bad["goals"][0]["met_deterministic"]


def test_tree_without_3a_is_unchanged():
    r = core.simulate(core.load_profile(), "1")
    assert r["metrics"]["final_pillar_3a"] == 0 and "pillar_3a" not in r["deterministic"]
    assert round(r["metrics"]["final_net_worth"]) == 125605  # same as after #48 item 3
