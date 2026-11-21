"""Bridge to the UBS starter kit format (phases + one-off costs).

Lets us prove that, under the starter kit's own assumptions (cash only, no
inflation, returns, taxes or shocks), our engine reproduces its numbers.
"""
from __future__ import annotations

from .assumptions import build_assumptions, zero_world_assumptions
from .simulate import simulate_node


def starter_to_inputs(profile: dict, scenario: dict) -> tuple[dict, list[dict]]:
    """Starter kit profile + scenario -> (Profile dict, interventions)."""
    prof = {
        "profile_id": "starter-" + str(profile.get("name", "x")).lower(),
        "display_name": profile.get("name", ""),
        "as_of": "2025-01-01",
        "horizon_months": profile["horizon_months"],
        "cash": profile["opening_cash_chf"],
        "monthly_net_income": 0, "monthly_rent": 0, "monthly_other_expenses": 0,
    }
    ivs: list[dict] = []
    for ph in scenario["phases"]:
        win = {"from_month": ph["start_month"], "to_month": ph["end_month"]}
        ivs.append({"param": "monthly_net_income", "op": "set", "value": ph["monthly_income_chf"], **win})
        ivs.append({"param": "monthly_other_expenses", "op": "set", "value": ph["monthly_expenses_chf"], **win})
    for c in scenario.get("one_off_costs", []):
        ivs.append({"param": "one_off_cost", "month": c["month"], "value": c["amount_chf"], "label": "one-off cost"})
    return prof, ivs


def simulate_starter(profile: dict, scenario: dict, n_paths: int = 50) -> dict:
    prof, ivs = starter_to_inputs(profile, scenario)
    aset = build_assumptions(base=zero_world_assumptions())
    return simulate_node(prof, ivs, assumptions=aset, node_id=scenario["name"], n_paths=n_paths)
