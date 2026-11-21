"""Regression checks for public-target selection and parameter acceptance."""
from unittest.mock import patch

from core.bench import optimise as opt
from core.bench import harness


def target(name, value, tolerance=0.001, param="real_wage_growth"):
    return {"id": name, "kind": "assumption", "param": param, "target": value,
            "tolerance": tolerance, "weight": 1, "status": "verified"}


def optimise_targets(targets):
    with patch.object(opt, "used_targets", return_value=targets), \
         patch.object(opt, "load_targets", return_value=targets), \
         patch.object(opt, "score", side_effect=lambda overrides: harness.score(overrides, targets=targets)):
        return opt.optimise()


def test_sources_and_rules_are_excluded():
    used = opt.used_targets()
    assert not {"balanced-return", "balanced-real-return"} & {t["id"] for t in used}
    space = opt.search_space(used + [target("tax-rule", 1.0, param="income_tax_scale")])
    assert "AS-income-tax" not in space
    assert "AS-investment-return" not in space


def test_fixed_seed_fit_is_reproducible_and_bounded():
    targets = [target("wage", 0.015)]
    space = opt.search_space(targets)
    first = opt.fit(targets, space)
    assert first == opt.fit(targets, space)
    assert opt.loss_of(first, targets) < opt.loss_of({}, targets)
    for key, value in first.items():
        assert space[key]["range"][0] <= value <= space[key]["range"][1]


def test_material_single_target_moves_but_small_gain_does_not():
    material = optimise_targets([target("wage", 0.015)])
    assert material["params"]["AS-real-wage-growth"]["moved"]
    small = optimise_targets([target("wage", 0.0101, tolerance=0.01)])
    assert not small["params"]["AS-real-wage-growth"]["moved"]
    assert small["sets"]["chosen"] == {}


def test_conflicting_targets_reject_material_move():
    result = optimise_targets([target("low-window", -0.004), target("high-window", 0.012)])
    wage = result["params"]["AS-real-wage-growth"]
    assert wage["loss_gain"] > wage["gain_needed"]
    assert wage["changes_side_without"]
    assert not wage["robust"] and not wage["moved"]
    assert result["sets"]["chosen"] == {}
