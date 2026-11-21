"""Payroll layer gross -> net (#48 item 2)."""
import numpy as np
import pytest

import core
from core.assumptions import build_assumptions
from core.models import Profile
from core.payroll import bvg_credit_rate, payroll

A = build_assumptions([]).values()

BASE = {"as_of": "2026-01-01", "horizon_months": 36, "cash": 20000, "monthly_rent": 1500,
        "monthly_other_expenses": 1500, "age": 30}


def test_2026_rates_are_verified_with_sources():
    recs = {a["param"]: a for a in core.default_assumptions() if a["param"].startswith("payroll_")}
    for p in ("payroll_ahv_iv_eo_rate", "payroll_alv_rate", "payroll_alv_cap", "payroll_bvg_entry",
              "payroll_bvg_coord", "payroll_bvg_max", "payroll_bvg_min_coord", "payroll_bvg_credit_25",
              "payroll_bvg_credit_55", "payroll_bvg_interest"):
        assert recs[p]["verified"] is True and "http" in recs[p]["source"] and recs[p]["retrieved"], p
    assert (A["payroll_ahv_iv_eo_rate"], A["payroll_alv_rate"], A["payroll_alv_cap"]) == (0.053, 0.011, 148200)
    assert (A["payroll_bvg_entry"], A["payroll_bvg_coord"], A["payroll_bvg_max"]) == (22680, 26460, 90720)
    # insurer-specific or fund-specific values are honestly marked as modelling choices
    assert recs["payroll_nbu_rate"]["verified"] is False and recs["payroll_bvg_employee_share"]["verified"] is False


def test_payslip_arithmetic_typical_salary():
    p = core.payslip(8000, 30)
    assert p["ahv_iv_eo"] == pytest.approx(0.053 * 8000)
    assert p["alv"] == pytest.approx(0.011 * 8000)
    coordinated = min(96000, 90720) - 26460  # 64,260
    assert p["bvg_employee"] + p["bvg_employer"] == pytest.approx(0.07 * coordinated / 12, abs=0.02)
    assert p["net"] == pytest.approx(p["gross"] - p["social"] - p["bvg_employee"], abs=0.02)


def test_alv_and_nbu_stop_at_the_insured_salary_cap():
    hi = payroll(np.array([20000.0]), np.array([40.0]), A)
    assert hi["alv"][0] == pytest.approx(0.011 * 148200 / 12)
    assert hi["nbu"][0] == pytest.approx(A["payroll_nbu_rate"] * 148200 / 12)
    assert hi["ahv_iv_eo"][0] == pytest.approx(0.053 * 20000)  # AHV has no cap


def test_bvg_thresholds_and_age_bands():
    below = payroll(np.array([22000 / 12]), np.array([30.0]), A)
    assert below["bvg_employee"][0] == 0.0  # under the entry threshold
    low = payroll(np.array([24000 / 12]), np.array([30.0]), A)  # coordinated salary floored at the minimum
    assert low["bvg_employee"][0] + low["bvg_employer"][0] == pytest.approx(0.07 * 3780 / 12)
    top = payroll(np.array([200000 / 12]), np.array([30.0]), A)  # capped at the upper limit
    assert top["bvg_employee"][0] + top["bvg_employer"][0] == pytest.approx(0.07 * (90720 - 26460) / 12)
    assert list(bvg_credit_rate([20, 25, 34.9, 35, 45, 55, 64.9, 65], A)) == [0, .07, .07, .10, .15, .18, .18, 0]


def test_under_25_pays_no_bvg():
    assert core.payslip(6000, 22)["bvg_employee"] == 0.0


def test_gross_node_equals_its_net_equivalent():
    gross = core.simulate_node({**BASE, "monthly_gross_income": 7000})
    net = core.simulate_node({**BASE, "monthly_net_income": core.payslip(7000, 30)["net"]})
    # same cash path up to rounding of the payslip and the age crossing no band in 3 years
    assert gross["metrics"]["final_cash"] == pytest.approx(net["metrics"]["final_cash"], abs=1.0)
    assert all(c["passed"] for c in gross["checks"]), gross["checks"]
    pr = gross["payroll"]
    assert pr["payslip"]["gross"] == 7000 and pr["in_net_worth"] is False
    flows = gross["deterministic"]["flows"]
    for k in ("gross_income", "social_contributions", "bvg_employee", "bvg_employer"):
        assert len(flows[k]) == 36
    assert flows["gross_income"][0] - flows["social_contributions"][0] - flows["bvg_employee"][0] == pytest.approx(
        flows["income"][0], abs=0.02)
    assert net["payroll"] is None and "gross_income" not in net["deterministic"]["flows"]


def test_bvg_balance_accumulates_credits_and_interest_outside_net_worth():
    r = core.simulate_node({**BASE, "monthly_gross_income": 7000,
                            "assets": [{"type": "pension_bvg", "value": 10000}]})
    bal = r["payroll"]["bvg_balance"]
    assert bal[0] == 10000 and len(bal) == 37
    credits = r["payroll"]["totals"]["bvg_employee"] + r["payroll"]["totals"]["bvg_employer"]
    assert bal[-1] > 10000 + credits  # interest on top of the credits
    plain = core.simulate_node({**BASE, "monthly_gross_income": 7000})
    assert r["metrics"]["final_net_worth"] == plain["metrics"]["final_net_worth"]  # locked, not counted


def test_gross_interventions_and_net_adjustments():
    prof = {**BASE, "monthly_gross_income": 6000}
    base = core.simulate_node(prof)
    bf = base["deterministic"]["flows"]
    wage = [g / 6000 for g in bf["gross_income"]]  # the engine's wage index on the deterministic path
    raise_ = core.simulate_node(prof, [{"param": "monthly_gross_income", "op": "set", "value": 8000, "from_month": 12}])
    rf = raise_["deterministic"]["flows"]
    assert rf["gross_income"][11] == pytest.approx(6000 * wage[11]) and rf["gross_income"][12] == pytest.approx(8000 * wage[12])
    assert rf["income"][12] / wage[12] == pytest.approx(core.payslip(8000, 31)["net"], abs=0.02)
    # a net "add" on a gross month adjusts the payroll's net, it does not replace it
    bonus = core.simulate_node(prof, [{"param": "monthly_net_income", "op": "add", "value": 100}])
    assert bonus["deterministic"]["flows"]["income"][0] == pytest.approx(bf["income"][0] + 100, abs=0.02)
    # a net "set" replaces the gross salary in its window (e.g. a job abroad paid net)
    swap = core.simulate_node(prof, [{"param": "monthly_net_income", "op": "set", "value": 3000, "from_month": 6}])
    sf = swap["deterministic"]["flows"]
    assert sf["gross_income"][6] == 0.0 and sf["gross_income"][5] > 0
    assert sf["income"][6] == pytest.approx(3000 * wage[6])


def test_invalid_combinations_are_rejected():
    with pytest.raises(ValueError, match="take_home"):
        Profile.from_dict({**BASE, "monthly_gross_income": 7000, "income_basis": "take_home"})
    with pytest.raises(ValueError, match="age"):
        core.simulate_node({k: v for k, v in BASE.items() if k != "age"} | {"monthly_gross_income": 7000})


def test_tree_profile_is_unchanged():
    """Alexia's tree stays on net salaries: no payroll block, same flows as before."""
    r = core.simulate(core.load_profile(), "0")
    assert r["payroll"] is None
    assert core.validation()["passed"] == core.validation()["total"]
