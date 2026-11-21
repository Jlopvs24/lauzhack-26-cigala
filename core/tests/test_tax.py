"""Income tax by place and household from the official ESTV tables (#48 item 3)."""
import json

import numpy as np
import pytest

import core
from core import tax
from core.models import Profile

D = tax.data()
BASE = {"as_of": "2026-01-01", "horizon_months": 48, "cash": 30000, "monthly_net_income": 6000,
        "monthly_rent": 1800, "monthly_other_expenses": 1500}


def test_tables_are_the_estv_points_with_provenance():
    assert D["tax_year"] == 2026 and "estv.admin.ch" in D["source"] and D["retrieved"]
    assert D["request_template"]["Confession1"] == 4  # no church tax
    # the table reproduces the stored ESTV amount exactly at every point
    for key, pts in D["tables"].items():
        city, hh = key.split("|")
        tb = tax.table({"city": city, "household": hh, "country": "CH"})
        xs, ys = [p[0] for p in tb], [p[1] for p in tb]
        for net, amount in pts:
            assert np.interp(net, xs, ys) * net == pytest.approx(amount, abs=0.01), key


def test_tax_amount_never_falls_as_income_rises():
    for key, pts in D["tables"].items():
        amounts = [t for _, t in pts]
        nets = [n for n, _ in pts]
        assert nets == sorted(nets) and all(b >= a for a, b in zip(amounts, amounts[1:])), key


def test_household_and_place_order():
    # a married single earner pays less than a single person, a family less again (same net)
    for city in D["locations"]:
        t = {hh: dict(map(tuple, D["tables"][f"{city}|{hh}"])) for hh in ("single", "couple", "family")}
        for net in t["single"]:
            if net > 40000:
                assert t["single"][net] >= t["couple"][net] >= t["family"][net], (city, net)
    # Zurich taxes a single CHF ~72,700 net salary less than Lausanne (ESTV 2026)
    lau = dict(map(tuple, D["tables"]["Lausanne|single"]))
    zur = dict(map(tuple, D["tables"]["Zurich|single"]))
    net = 72686
    assert zur[net] < lau[net]


def test_resolve_city_canton_default():
    assert tax.resolve("Zürich")["city"] == "Zurich"
    assert tax.resolve("Genève", household_type="family")["household"] == "family"
    assert tax.resolve(None, "TI") | {} == tax.resolve(None, "TI") and tax.resolve(None, "TI")["city"] == "Lugano"
    r = tax.resolve("Sion", "VS")
    assert r["city"] == "Lausanne" and r["fallback"] is True  # never a silent fallback
    assert tax.resolve("Bern")["fallback"] is False
    assert tax.resolve(household_type="shared_housing")["household"] == "single"
    assert tax.resolve(country="DE")["source"] == "assumption:tax_abroad_rate"
    with pytest.raises(ValueError, match="household_type"):
        Profile.from_dict({**BASE, "household_type": "polycule"})


def test_profile_residence_drives_the_tax_and_is_reported():
    lau = core.simulate_node({**BASE, "city": "Lausanne"})
    zur = core.simulate_node({**BASE, "city": "Zurich", "canton": "ZH"})
    fam = core.simulate_node({**BASE, "city": "Lausanne", "household_type": "family"})
    assert zur["metrics"]["total_income_tax"] < lau["metrics"]["total_income_tax"]
    assert fam["metrics"]["total_income_tax"] < lau["metrics"]["total_income_tax"]
    seg = zur["tax_residence"]
    assert len(seg) == 1 and seg[0]["city"] == "Zurich" and seg[0]["from_month"] == 0 and seg[0]["to_month"] == 48
    none = core.simulate_node({**BASE})
    assert none["tax_residence"][0]["fallback"] is True  # no city given: Lausanne, and says so
    th = core.simulate_node({**BASE, "income_basis": "take_home"})
    assert th["tax_residence"][0]["taxed"] is False and th["metrics"]["total_income_tax"] == 0


def test_tax_residence_intervention_switches_tables_by_month():
    ivs = [{"param": "tax_residence", "city": "Zurich", "from_month": 12},
           {"param": "tax_residence", "country": "DE", "from_month": 30, "to_month": 40}]
    r = core.simulate_node({**BASE, "city": "Lausanne"}, ivs)
    segs = [(s["from_month"], s["to_month"], s["city"] or s["country"]) for s in r["tax_residence"]]
    assert segs == [(0, 12, "Lausanne"), (12, 30, "Zurich"), (30, 40, "DE"), (40, 48, "Zurich")]
    f = r["deterministic"]["flows"]
    rate = [t / i for t, i in zip(f["income_tax"], f["income"])]
    A = core.build_assumptions([]).values()
    assert rate[35] == pytest.approx(A["tax_abroad_rate"], abs=1e-4)  # flows are rounded to cents
    lau = core.simulate_node({**BASE, "city": "Lausanne"})["deterministic"]["flows"]
    assert f["income_tax"][5] == pytest.approx(lau["income_tax"][5])  # untouched before the move
    assert all(c["passed"] for c in r["checks"])
    # household-only change keeps the place
    wed = core.simulate_node({**BASE, "city": "Zurich"}, [{"param": "tax_residence", "household": "couple", "from_month": 24}])
    assert [(s["city"], s["household"]) for s in wed["tax_residence"]] == [("Zurich", "single"), ("Zurich", "couple")]
    with pytest.raises(ValueError, match="household"):
        core.simulate_node(BASE, [{"param": "tax_residence", "household": "x"}])
    with pytest.raises(ValueError, match="give city"):
        core.simulate_node(BASE, [{"param": "tax_residence", "from_month": 3}])


def test_tree_inheritance_abroad_then_zurich():
    prof = core.load_profile()
    r3 = core.simulate(prof, "3")
    assert [(s["from_month"], s["to_month"], s["country"]) for s in r3["tax_residence"]] == [(0, 120, "abroad")]
    r312 = core.simulate(prof, "3.1.2")
    assert [s["country"] for s in r312["tax_residence"]] == ["abroad"]
    r333 = core.simulate(prof, "3.3.3")
    assert [(s["from_month"], s["to_month"], s["city"] or s["country"]) for s in r333["tax_residence"]] == [
        (0, 36, "abroad"), (36, 120, "Zurich")]
    r1 = core.simulate(prof, "1")
    assert [s["city"] for s in r1["tax_residence"]] == ["Lausanne"] and r1["tax_residence"][0]["fallback"] is False


def test_residence_changes_through_the_batched_paths():
    ivs = [{"param": "tax_residence", "city": "Geneva", "from_month": 12},
           {"param": "monthly_net_income", "op": "add", "value": 500, "from_month": 12}]
    r = core.simulate_node({**BASE, "city": "Lausanne"}, ivs, own_interventions=ivs,
                           exploration=True, uncertainty=True, sensitivity=True, n_paths=200)
    assert all(c["passed"] for c in r["checks"]), r["checks"]
    assert r["exploration"] is not None and r["sensitivity"]
    # the timing analysis delays the move too (tax_residence has a from_month)
    from core.explore import shift_interventions
    assert shift_interventions(ivs, 12, 48)[0]["from_month"] == 24


def test_default_table_is_lausanne_single():
    aset = core.build_assumptions([])
    assert aset.tax_table() == tax.table(tax.resolve("Lausanne"))
