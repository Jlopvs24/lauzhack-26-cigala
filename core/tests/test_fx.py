"""Move abroad in EUR (#48 item 5): amounts in EUR converted each month at the EURCHF path."""
import pytest

import core

FX = 0.9223
BASE = {"as_of": "2026-01-01", "horizon_months": 36, "cash": 20000, "monthly_net_income": 5000,
        "monthly_rent": 1500, "monthly_other_expenses": 1500, "city": "Lausanne"}
ABROAD = [{"param": "monthly_net_income", "op": "set", "value": 4000, "currency": "EUR", "from_month": 0},
          {"param": "monthly_rent", "op": "set", "value": 1300, "currency": "EUR", "from_month": 0},
          {"param": "tax_residence", "country": "DE", "from_month": 0}]


def test_rate_is_sourced():
    a = next(x for x in core.default_assumptions() if x["id"] == "AS-eurchf")
    assert a["value"] == FX and a["verified"] and "ecb.europa.eu" in a["source"]


def test_constant_rate_reproduces_the_chf_equivalent():
    eur = core.simulate_node(BASE, ABROAD)
    chf = core.simulate_node(BASE, [{"param": "monthly_net_income", "op": "set", "value": 4000 * FX, "from_month": 0},
                                    {"param": "monthly_rent", "op": "set", "value": 1300 * FX, "from_month": 0},
                                    ABROAD[2]])
    assert eur["metrics"]["final_net_worth"] == pytest.approx(chf["metrics"]["final_net_worth"], abs=0.05)
    assert all(c["passed"] for c in eur["checks"])
    f = eur["deterministic"]["flows"]
    assert f["eurchf"][0] == FX and f["income_eur"][0] == pytest.approx(4000)
    assert f["spending_eur"][0] == pytest.approx(1300)
    assert "eurchf" not in core.simulate_node(BASE)["deterministic"]["flows"]  # CHF-only: no FX lines


def test_fx_weather_moves_only_eur_amounts():
    base = core.simulate_node(BASE, ABROAD)
    strong = core.simulate_node(BASE, ABROAD, weather=[{"type": "chf_strengthens", "start_month": 12}])
    f, g = base["deterministic"]["flows"], strong["deterministic"]["flows"]
    assert g["eurchf"][11] == FX and g["eurchf"][12] == pytest.approx(FX * 0.9, abs=1e-4)  # 4 decimals
    assert g["income"][12] == pytest.approx(f["income"][12] * 0.9, abs=0.02)  # flows in cents
    assert g["living_expenses"][12] < f["living_expenses"][12]  # EUR rent costs fewer francs
    # net: salary 4000 > spending in EUR, so a strong franc hurts
    assert strong["metrics"]["final_net_worth"] < base["metrics"]["final_net_worth"]
    weak = core.simulate_node(BASE, ABROAD, weather=[{"type": "chf_weakens"}])
    assert weak["metrics"]["final_net_worth"] > base["metrics"]["final_net_worth"]
    plain = core.simulate_node(BASE)
    plain_w = core.simulate_node(BASE, weather=[{"type": "chf_strengthens"}])
    assert plain_w["metrics"]["final_net_worth"] == plain["metrics"]["final_net_worth"]  # nothing in EUR


def test_mixing_and_replacing_currencies():
    # coming back: a CHF set replaces the EUR amount in its window
    back = core.simulate_node(BASE, ABROAD + [{"param": "monthly_net_income", "op": "set", "value": 6000, "from_month": 24}])
    f = back["deterministic"]["flows"]
    assert f["income_eur"][24] == 0 and f["income_eur"][23] > 0
    # a CHF add on an EUR rent adds francs to the converted amount
    mix = core.simulate_node(BASE, ABROAD + [{"param": "monthly_rent", "op": "add", "value": -100, "from_month": 0}])
    assert mix["deterministic"]["flows"]["living_expenses"][0] == pytest.approx(1300 * FX - 100 + 1500, abs=0.02)
    # a one-off in EUR
    dep = core.simulate_node(BASE, ABROAD + [{"param": "one_off_cost", "month": 0, "value": 2000, "currency": "EUR", "label": "Deposit"}])
    assert dep["deterministic"]["flows"]["one_off_cost"][0] == pytest.approx(2000 * FX)
    assert any(e.get("currency") == "EUR" for e in dep["events"])


def test_invalid_currency_uses_are_rejected():
    with pytest.raises(ValueError, match="currency"):
        core.simulate_node(BASE, [{"param": "monthly_rent", "op": "set", "value": 1, "currency": "USD"}])
    with pytest.raises(ValueError, match="only supported"):
        core.simulate_node(BASE, [{"param": "monthly_pillar_3a", "op": "set", "value": 100, "currency": "EUR"}])
    with pytest.raises(ValueError, match="only supported"):
        core.simulate_node({**BASE, "age": 30}, [{"param": "monthly_gross_income", "op": "set", "value": 1, "currency": "EUR"}])


def test_batched_paths_with_eur():
    r = core.simulate_node(BASE, ABROAD, own_interventions=ABROAD, exploration=True, uncertainty=True,
                           sensitivity=True, n_paths=200, weather=[{"type": "chf_strengthens", "start_month": 6}])
    assert all(c["passed"] for c in r["checks"]), r["checks"]
    rows = {row["assumption_id"]: row for row in r["sensitivity"]}
    assert "AS-eurchf" in rows and rows["AS-eurchf"]["delta_final_net_worth"] != 0


def test_tree_abroad_branch_in_eur_and_return_taxed_in_lausanne():
    prof = core.load_profile()
    r3 = core.simulate(prof, "3")
    f = r3["deterministic"]["flows"]
    assert f["eurchf"][0] == FX and f["income_eur"][0] == pytest.approx(4012)
    assert f["income"][0] == pytest.approx(4012 * FX, abs=0.02)  # = the kit's CHF 3,700 up to rounding
    r33 = core.simulate(prof, "3.3")
    assert [(s["from_month"], s["city"] or s["country"]) for s in r33["tax_residence"]] == [(0, "abroad"), (36, "Lausanne")]
    assert r33["deterministic"]["flows"]["income_eur"][36] == 0
    strong = core.simulate(prof, "3", weather=[{"type": "chf_strengthens"}])
    assert strong["metrics"]["final_net_worth"] < r3["metrics"]["final_net_worth"]
