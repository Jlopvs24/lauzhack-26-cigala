"""Typed inputs of the engine, parsed from the JSON contracts (docs/contracts.md).

Every public engine function accepts plain JSON-like dicts and returns plain
JSON-serialisable dicts. These dataclasses only validate and normalise input.

Conventions: CHF, months indexed 0..H-1 from ``as_of``, half-open month windows
``[from_month, to_month)``, rates as decimals (0.05 = 5 %).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

SERIES_PARAMS = (
    "monthly_net_income",
    "monthly_rent",
    "monthly_other_expenses",
    "monthly_investment_contribution",
)
EVENT_PARAMS = ("one_off_cost", "one_off_income", "new_liability", "loan_change", "cancel_one_off")
MODEL_PARAMS = ("assumption",)  # node-level assumption values, applied by AssumptionSet.with_node_values
OPS = ("set", "add", "mul")
# What "monthly_net_income" means (#48 item 1). net_before_tax: after social contributions, before
# income tax (the Swiss payslip "Nettolohn"; residents pay income tax separately), so the engine
# charges income tax. take_home: what is left after income tax too, so no income tax is charged
# again. Our tree uses net_before_tax; imported UBS synthetic profiles use take_home unless stated
# (their ledgers have no tax line).
INCOME_BASES = ("net_before_tax", "take_home")
NO_TAX = [[0, 0.0]]


def num(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number, got {value!r}")
    out = float(value)
    if out != out or out in (float("inf"), float("-inf")):
        raise ValueError(f"{label} must be finite")
    if minimum is not None and out < minimum:
        raise ValueError(f"{label} must be >= {minimum}, got {out}")
    return out


def month_int(value: Any, label: str, horizon: int, *, allow_end: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer month index, got {value!r}")
    upper = horizon if allow_end else horizon - 1
    if not 0 <= value <= upper:
        raise ValueError(f"{label}={value} outside 0..{upper}")
    return value


def months_between(start: date, end: date) -> int:
    """Index of the month containing ``end`` counted from the month of ``start``."""
    return (end.year - start.year) * 12 + (end.month - start.month)


@dataclass(frozen=True)
class Liability:
    type: str
    principal: float
    annual_rate: float
    monthly_payment: float
    label: str = ""
    start_month: int = 0
    is_new: bool = False  # True for loans taken by an intervention (cash received at start_month)
    payment_start_month: int = 0  # payments before this month are deferred (interest capitalised)
    changes: tuple = ()  # ((month, monthly_payment | None, annual_rate | None), ...) from loan_change

    @staticmethod
    def from_dict(d: dict, label: str = "liability", start_month: int = 0, is_new: bool = False) -> "Liability":
        return Liability(
            type=str(d.get("type", "loan")),
            principal=num(d.get("principal", 0), f"{label}.principal", minimum=0),
            annual_rate=num(d.get("annual_rate", 0), f"{label}.annual_rate", minimum=0),
            monthly_payment=num(d.get("monthly_payment", 0), f"{label}.monthly_payment", minimum=0),
            label=str(d.get("label", d.get("type", "loan"))),
            start_month=start_month,
            is_new=is_new,
            payment_start_month=int(d.get("payment_start_month", start_month + 1 if is_new else 0)),
        )


@dataclass(frozen=True)
class Goal:
    name: str
    target: float
    target_month: int  # month index whose END balance is tested
    priority: str = "medium"
    metric: str = "liquid"  # "liquid" = cash + investments, "net_worth" = minus debt


@dataclass(frozen=True)
class Profile:
    profile_id: str
    display_name: str
    as_of: date
    horizon_months: int
    cash: float
    monthly_net_income: float
    monthly_rent: float
    monthly_other_expenses: float
    monthly_investment_contribution: float
    investments: float
    liabilities: tuple[Liability, ...]
    goals: tuple[Goal, ...]
    raw: dict = field(compare=False, repr=False, default_factory=dict)
    income_basis: str = "net_before_tax"

    def tax_table(self, aset) -> list[list[float]]:
        """The income-tax table the engine applies to this profile's income."""
        return NO_TAX if self.income_basis == "take_home" else aset.tax_table()

    @staticmethod
    def from_dict(d: dict) -> "Profile":
        horizon = d.get("horizon_months", 120)
        if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 600:
            raise ValueError("horizon_months must be an integer in 1..600")
        as_of = date.fromisoformat(str(d.get("as_of", "2025-01-01")))
        basis = str(d.get("income_basis", "net_before_tax"))
        if basis not in INCOME_BASES:
            raise ValueError(f"income_basis must be one of {INCOME_BASES}, got {basis!r}")
        investments = 0.0
        for i, a in enumerate(d.get("assets", []) or []):
            value = num(a.get("value", 0), f"assets[{i}].value", minimum=0)
            if a.get("type", "investment") in ("investment", "investment_portfolio", "pension_3a"):
                investments += value
            # other asset types (property, car...) are out of scope for v1
        liabilities = tuple(
            Liability.from_dict(x, f"liabilities[{i}]")
            for i, x in enumerate(d.get("liabilities", []) or [])
            if num(x.get("principal", 0), f"liabilities[{i}].principal", minimum=0) > 0
        )
        goals = []
        for i, g in enumerate(d.get("goals", []) or []):
            tm = months_between(as_of, date.fromisoformat(str(g["target_date"])))
            goals.append(Goal(
                name=str(g["name"]),
                target=num(g["target"], f"goals[{i}].target", minimum=0),
                target_month=min(max(tm, 0), horizon - 1),
                priority=str(g.get("priority", "medium")),
                metric=str(g.get("metric", "liquid")),
            ))
        return Profile(
            profile_id=str(d.get("profile_id", "anonymous")),
            display_name=str(d.get("display_name", "")),
            as_of=as_of,
            horizon_months=horizon,
            cash=num(d.get("cash", 0), "cash"),
            monthly_net_income=num(d.get("monthly_net_income", 0), "monthly_net_income", minimum=0),
            monthly_rent=num(d.get("monthly_rent", 0), "monthly_rent", minimum=0),
            monthly_other_expenses=num(d.get("monthly_other_expenses", 0), "monthly_other_expenses", minimum=0),
            monthly_investment_contribution=num(
                d.get("monthly_investment_contribution", 0), "monthly_investment_contribution", minimum=0),
            investments=investments,
            liabilities=liabilities,
            goals=tuple(goals),
            raw=d,
            income_basis=basis,
        )


@dataclass(frozen=True)
class Intervention:
    param: str
    op: str = "set"
    value: float = 0.0
    from_month: int = 0
    to_month: int | None = None  # exclusive; None = end of horizon
    month: int = 0  # for events
    label: str = ""
    liability: Liability | None = None
    loan: str = ""  # loan_change: label of the loan to change
    monthly_payment: float | None = None
    annual_rate: float | None = None


def resolve_value(value: Any, assumptions: dict[str, float], label: str) -> float:
    """A value is a number or ``{"assumption": "<id or param>", "scale": k}``."""
    if isinstance(value, dict) and "assumption" in value:
        key = value["assumption"]
        if key not in assumptions:
            raise ValueError(f"{label} references unknown assumption {key!r}")
        return assumptions[key] * num(value.get("scale", 1), f"{label}.scale")
    return num(value, label)


def parse_interventions(items: list[dict], assumptions: dict[str, float], horizon: int,
                        where: str = "interventions") -> list[Intervention]:
    out = []
    for i, it in enumerate(items or []):
        lab = f"{where}[{i}]"
        param = it.get("param")
        if param in SERIES_PARAMS:
            op = it.get("op", "set")
            if op not in OPS:
                raise ValueError(f"{lab}.op must be one of {OPS}")
            start = month_int(it.get("from_month", 0), f"{lab}.from_month", horizon)
            end = it.get("to_month")
            end = horizon if end is None else month_int(min(end, horizon), f"{lab}.to_month", horizon, allow_end=True)
            if end <= start:
                raise ValueError(f"{lab}: to_month must be > from_month")
            out.append(Intervention(param=param, op=op, value=resolve_value(it.get("value", 0), assumptions, f"{lab}.value"),
                                    from_month=start, to_month=end, label=str(it.get("label", ""))))
        elif param in ("one_off_cost", "one_off_income"):
            m = month_int(it.get("month", 0), f"{lab}.month", horizon)
            v = resolve_value(it.get("value", 0), assumptions, f"{lab}.value")
            if v < 0:
                raise ValueError(f"{lab}.value cannot be negative (use the other event type)")
            out.append(Intervention(param=param, op="add", value=v, month=m, label=str(it.get("label", param))))
        elif param == "new_liability":
            m = month_int(it.get("month", 0), f"{lab}.month", horizon)
            spec = dict(it.get("liability", {}))
            if isinstance(spec.get("principal"), dict):
                spec["principal"] = resolve_value(spec["principal"], assumptions, f"{lab}.liability.principal")
            if isinstance(spec.get("annual_rate"), dict):
                spec["annual_rate"] = resolve_value(spec["annual_rate"], assumptions, f"{lab}.liability.annual_rate")
            if isinstance(spec.get("monthly_payment"), dict):
                spec["monthly_payment"] = resolve_value(spec["monthly_payment"], assumptions, f"{lab}.liability.monthly_payment")
            liab = Liability.from_dict(spec, f"{lab}.liability", start_month=m, is_new=True)
            out.append(Intervention(param=param, month=m, liability=liab, label=str(it.get("label", liab.label))))
        elif param == "loan_change":
            m = month_int(it.get("month", 0), f"{lab}.month", horizon)
            if not it.get("loan"):
                raise ValueError(f"{lab}.loan (label of the loan to change) is required")
            pay = it.get("monthly_payment")
            rate = it.get("annual_rate")
            if pay is None and rate is None:
                raise ValueError(f"{lab}: set monthly_payment and/or annual_rate")
            pay = None if pay is None else resolve_value(pay, assumptions, f"{lab}.monthly_payment")
            rate = None if rate is None else resolve_value(rate, assumptions, f"{lab}.annual_rate")
            for v, name in ((pay, "monthly_payment"), (rate, "annual_rate")):
                if v is not None and v < 0:
                    raise ValueError(f"{lab}.{name} cannot be negative")
            out.append(Intervention(param=param, month=m, loan=str(it["loan"]), monthly_payment=pay,
                                    annual_rate=rate, label=str(it.get("label", "Loan change"))))
        elif param == "cancel_one_off":
            if not it.get("label"):
                raise ValueError(f"{lab}.label (label of the one-off to cancel) is required")
            out.append(Intervention(param=param, label=str(it["label"])))
        elif param in MODEL_PARAMS:
            continue  # resolved into the assumption set before parsing
        else:
            raise ValueError(f"{lab}.param {param!r} not supported; use one of {SERIES_PARAMS + EVENT_PARAMS + MODEL_PARAMS}")
    return out
