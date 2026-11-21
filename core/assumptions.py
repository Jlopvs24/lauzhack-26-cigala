"""Assumption sets: every model parameter is an explicit, sourced, editable value.

An ``AssumptionSet`` is an ordered list of Assumption dicts (contract in
docs/contracts.md). Overrides are ``{id_or_param: new_value}``.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable

from .models import num

DATA = Path(__file__).resolve().parent / "data"

REQUIRED_PARAMS = (
    "inflation_mean", "inflation_sd", "real_wage_growth", "investment_return_mean",
    "investment_return_vol", "cash_interest_rate", "job_loss_annual_prob",
    "unemployment_mean_duration_months", "unemployment_replacement_rate",
    "unexpected_expense_annual_prob", "unexpected_expense_mean", "income_tax_scale",
    "auto_liquidate_investments", "liquidity_target_months", "debt_service_limit",
)


def default_assumptions() -> list[dict]:
    """The Swiss default set (fresh copy, safe to mutate)."""
    return json.loads((DATA / "assumptions_ch.json").read_text(encoding="utf-8"))["assumptions"]


def as_override_dict(overrides: dict[str, Any] | list[dict] | None) -> dict[str, Any]:
    """Accept ``{id_or_param: value}`` or the API form ``[{"id": ..., "value": ...}]``."""
    if not overrides:
        return {}
    if isinstance(overrides, list):
        return {o.get("id") or o.get("param"): o["value"] for o in overrides}
    return dict(overrides)


class AssumptionSet:
    def __init__(self, items: Iterable[dict], overrides: dict[str, Any] | list[dict] | None = None):
        self.items: list[dict] = []
        seen: dict[str, int] = {}
        for a in items:
            a = copy.deepcopy(a)
            for k in ("id", "param", "value"):
                if k not in a:
                    raise ValueError(f"assumption {a!r} is missing '{k}'")
            num(a["value"], f"assumption {a['id']}.value")
            if a["id"] in seen:  # later sets (e.g. tree-specific) replace earlier ones
                self.items[seen[a["id"]]] = a
            else:
                seen[a["id"]] = len(self.items)
                self.items.append(a)
        self.overridden: list[str] = []
        overrides = as_override_dict(overrides)
        for key, value in overrides.items():
            target = self._find(key)
            if target is None:
                raise ValueError(f"override for unknown assumption {key!r}")
            target["default_value"] = target.get("default_value", target["value"])
            target["value"] = num(value, f"override {key}")
            target["kind"] = target.get("kind", "assumption")
            target["user_edited"] = True
            self.overridden.append(target["id"])

    def _find(self, key: str) -> dict | None:
        for a in self.items:
            if a["id"] == key or a["param"] == key:
                return a
        return None

    def get(self, key: str) -> dict:
        a = self._find(key)
        if a is None:
            raise KeyError(key)
        return a

    def values(self) -> dict[str, float]:
        """Lookup table by id AND by param name (both point to the same value)."""
        out: dict[str, float] = {}
        for a in self.items:
            out[a["id"]] = float(a["value"])
            out[a["param"]] = float(a["value"])
        return out

    def tax_table(self) -> list[list[float]]:
        a = self._find("income_tax_scale")
        return a.get("table", [[0, 0.0]]) if a else [[0, 0.0]]

    def with_overrides(self, overrides: dict[str, Any] | list[dict]) -> "AssumptionSet":
        merged = {a["id"]: a["value"] for a in self.items if a.get("user_edited")}
        merged.update(as_override_dict(overrides))
        base = [dict(a, value=a.get("default_value", a["value"])) for a in self.items]
        for a in base:
            a.pop("default_value", None)
            a.pop("user_edited", None)
        return AssumptionSet(base, merged)

    def check_complete(self) -> list[str]:
        vals = self.values()
        return [p for p in REQUIRED_PARAMS if p not in vals]

    def to_list(self) -> list[dict]:
        return copy.deepcopy(self.items)


def build_assumptions(extra: Iterable[dict] = (), overrides: dict[str, Any] | list[dict] | None = None,
                      base: Iterable[dict] | None = None) -> AssumptionSet:
    items = list(default_assumptions() if base is None else base) + list(extra)
    aset = AssumptionSet(items, overrides)
    missing = aset.check_complete()
    if missing:
        raise ValueError(f"assumption set is missing params: {missing}")
    return aset


def zero_world_assumptions() -> list[dict]:
    """Same parameters with every macro effect switched off (inflation, returns,
    taxes, shocks). Used to reproduce the UBS starter kit, which is cash-only."""
    items = default_assumptions()
    zero = {"inflation_mean", "inflation_sd", "real_wage_growth", "investment_return_mean",
            "investment_return_vol", "cash_interest_rate", "job_loss_annual_prob",
            "unexpected_expense_annual_prob", "income_tax_scale"}
    for a in items:
        if a["param"] in zero:
            a["value"] = 0
            a["source"] = "Switched off to match the UBS starter kit (cash-only, no inflation/returns/tax)"
    return items
