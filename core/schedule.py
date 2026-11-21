"""Turn a Profile plus a list of Interventions into month-by-month plans.

A Schedule holds the *planned* amounts at today's prices (before inflation,
market moves and shocks, which the engine adds) and the debt schedule.
Interventions are applied in order, so a child node's interventions refine
its parent's.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from .models import Intervention, Liability, Profile
from .payroll import payroll


@dataclass
class Schedule:
    horizon: int
    income: np.ndarray            # planned net income (after social contributions, before income tax)
    rent: np.ndarray
    other_expenses: np.ndarray
    investment_contribution: np.ndarray
    one_off_cost: np.ndarray
    one_off_income: np.ndarray
    liabilities: list[Liability]
    events: list[dict] = field(default_factory=list)  # human-readable log of one-off events
    # payroll (#48 item 2), today's prices, 0 where the month has no gross salary
    gross: np.ndarray | None = None
    social: np.ndarray | None = None
    bvg_employee: np.ndarray | None = None
    bvg_employer: np.ndarray | None = None

    @property
    def expenses(self) -> np.ndarray:
        return self.rent + self.other_expenses


def build_schedule(profile: Profile, interventions: list[Intervention], A: dict | None = None) -> Schedule:
    """``A`` (assumption values) is needed only when a gross salary is used (payroll rates)."""
    H = profile.horizon_months
    gross = np.full(H, profile.monthly_gross_income)
    add_adj, mul_adj = np.zeros(H), np.ones(H)  # net add/mul on months paid from a gross salary
    series = {
        "monthly_net_income": np.full(H, profile.monthly_net_income),
        "monthly_rent": np.full(H, profile.monthly_rent),
        "monthly_other_expenses": np.full(H, profile.monthly_other_expenses),
        "monthly_investment_contribution": np.full(H, profile.monthly_investment_contribution),
    }
    one_off_cost = np.zeros(H)
    one_off_income = np.zeros(H)
    liabilities = list(profile.liabilities)
    events: list[dict] = []
    for iv in interventions:
        if iv.param == "monthly_gross_income":
            window = slice(iv.from_month, iv.to_month)
            if iv.op == "set":
                gross[window] = iv.value
                add_adj[window], mul_adj[window] = 0.0, 1.0
            elif iv.op == "add":
                gross[window] += iv.value
            else:
                gross[window] *= iv.value
            np.maximum(gross, 0.0, out=gross)
            continue
        if iv.param == "monthly_net_income" and iv.op != "set" and (gross[iv.from_month:iv.to_month] > 0).any():
            idx = np.arange(iv.from_month, iv.to_month)
            paid = idx[gross[idx] > 0]  # adjust the net that the payroll produces
            plain = idx[gross[idx] <= 0]
            if iv.op == "add":
                add_adj[paid] += iv.value
                series["monthly_net_income"][plain] += iv.value
            else:
                mul_adj[paid] *= iv.value
                add_adj[paid] *= iv.value
                series["monthly_net_income"][plain] *= iv.value
            np.maximum(series["monthly_net_income"], 0.0, out=series["monthly_net_income"])
            continue
        if iv.param == "monthly_net_income" and iv.op == "set":  # a net salary replaces a gross one
            gross[iv.from_month:iv.to_month] = 0.0
        if iv.param in series:
            s = series[iv.param]
            window = slice(iv.from_month, iv.to_month)
            if iv.op == "set":
                s[window] = iv.value
            elif iv.op == "add":
                s[window] += iv.value
            else:
                s[window] *= iv.value
            np.maximum(s, 0.0, out=s)  # a planned income/expense never goes below zero
        elif iv.param == "one_off_cost":
            one_off_cost[iv.month] += iv.value
            events.append({"month": iv.month, "type": "cost", "amount": iv.value, "label": iv.label})
        elif iv.param == "one_off_income":
            one_off_income[iv.month] += iv.value
            events.append({"month": iv.month, "type": "income", "amount": iv.value, "label": iv.label})
        elif iv.param == "new_liability" and iv.liability is not None:
            liabilities.append(iv.liability)
            events.append({"month": iv.month, "type": "loan", "amount": iv.liability.principal,
                           "label": iv.label})
        elif iv.param == "cancel_one_off":
            hits = [e for e in events if e["type"] in ("cost", "income") and e["label"] == iv.label]
            if not hits:
                raise ValueError(f"cancel_one_off: no one-off labelled {iv.label!r} on this path")
            for e in hits:
                (one_off_cost if e["type"] == "cost" else one_off_income)[e["month"]] -= e["amount"]
                events.remove(e)
        elif iv.param == "loan_change":
            k = next((j for j in range(len(liabilities) - 1, -1, -1) if liabilities[j].label == iv.loan), None)
            if k is None:
                raise ValueError(f"loan_change: no loan labelled {iv.loan!r} on this path")
            liabilities[k] = replace(liabilities[k], changes=liabilities[k].changes +
                                     ((iv.month, iv.monthly_payment, iv.annual_rate),))
            events.append({"month": iv.month, "type": "loan_change", "loan": iv.loan, "label": iv.label,
                           "monthly_payment": iv.monthly_payment, "annual_rate": iv.annual_rate})
    pay = None
    if (gross > 0).any():
        if A is None:
            raise ValueError("a gross salary needs the assumption values (payroll rates)")
        if profile.age is None:
            raise ValueError("a gross salary needs the profile's age (BVG age credits)")
        pay = payroll(gross, profile.age + np.arange(H) / 12.0, A)
        m = gross > 0
        series["monthly_net_income"][m] = np.maximum(pay["net"][m] * mul_adj[m] + add_adj[m], 0.0)
    return Schedule(
        horizon=H,
        gross=None if pay is None else pay["gross"],
        social=None if pay is None else pay["social"],
        bvg_employee=None if pay is None else pay["bvg_employee"],
        bvg_employer=None if pay is None else pay["bvg_employer"],
        income=series["monthly_net_income"],
        rent=series["monthly_rent"],
        other_expenses=series["monthly_other_expenses"],
        investment_contribution=series["monthly_investment_contribution"],
        one_off_cost=one_off_cost,
        one_off_income=one_off_income,
        liabilities=liabilities,
        events=events,
    )


@dataclass
class DebtSchedule:
    balance: np.ndarray    # (H+1,) total outstanding principal, [0] = opening
    payment: np.ndarray    # (H,) cash paid to lenders
    interest: np.ndarray   # (H,) interest accrued (an expense)
    proceeds: np.ndarray   # (H,) new borrowing received in cash
    per_liability: list[dict]


def debt_schedule(liabilities: list[Liability], H: int) -> DebtSchedule:
    """Fixed-payment amortisation, monthly rate = annual_rate / 12.

    interest_t = D_t * i; paid_t = min(payment, D_t + interest_t);
    D_{t+1} = D_t + interest_t - paid_t. If the payment is below the interest,
    the unpaid interest is capitalised (debt grows). Principal never goes negative.
    A loan taken at month m is received in cash in month m; payments start at
    ``payment_start_month`` (default m+1), earlier interest is capitalised.
    """
    balance = np.zeros(H + 1)
    payment = np.zeros(H)
    interest = np.zeros(H)
    proceeds = np.zeros(H)
    per = []
    for liab in liabilities:
        i = liab.annual_rate / 12.0
        pay = liab.monthly_payment
        changes = sorted(liab.changes, key=lambda c: c[0])
        d = 0.0 if liab.is_new else liab.principal
        bal = np.zeros(H + 1)
        bal[0] = d
        for t in range(H):
            if liab.is_new and t == liab.start_month:
                d += liab.principal
                proceeds[t] += liab.principal
                bal[t + 1] = d
                continue
            for month, new_pay, new_rate in changes:
                if month == t:
                    pay = pay if new_pay is None else new_pay
                    i = i if new_rate is None else new_rate / 12.0
            accrued = d * i
            due = pay if t >= liab.payment_start_month else 0.0
            paid = min(due, d + accrued)
            d = d + accrued - paid
            if d < 1e-9:
                d = 0.0
            interest[t] += accrued
            payment[t] += paid
            bal[t + 1] = d
        balance += bal
        paid_off = next((t for t in range(1, H + 1) if bal[t] == 0 and bal[t - 1] > 0), None)
        per.append({"label": liab.label, "type": liab.type, "principal": liab.principal,
                    "annual_rate": liab.annual_rate, "monthly_payment": liab.monthly_payment,
                    "start_month": liab.start_month, "payment_start_month": liab.payment_start_month, "paid_off_month": None if paid_off is None else paid_off - 1,
                    "changes": [{"month": m, "monthly_payment": p, "annual_rate": r} for m, p, r in changes],
                    "final_balance": round(float(bal[-1]), 2)})
    return DebtSchedule(balance, payment, interest, proceeds, per)

