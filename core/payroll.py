"""Swiss payroll: gross salary -> net salary (#48 item 2).

Employee deductions on a monthly gross salary, at today's prices (the engine applies wage
growth afterwards, like for net incomes):
- AHV/IV/EO: a flat share of the gross salary (no cap);
- ALV and non-occupational accident insurance (NBU): a share of the salary up to the
  insured-salary cap (CHF 148,200/year in 2026);
- BVG (pillar 2): age credits on the coordinated salary, i.e. the annual salary clipped to
  the BVG upper limit minus the coordination deduction (at least the minimum coordinated
  salary), only when the annual salary reaches the entry threshold; the employee pays
  ``payroll_bvg_employee_share`` of the credits, the employer the rest. No credits before 25.

Simplifications (documented in core/ENGINE_AUDIT.md): BVG risk premiums and pension-fund
extras above the legal minimum are ignored; age bands are the men's (women's bands differ by
one to three years); the salary is assumed to be the only job (no splitting across employers).
Every rate is an assumption in core/data/assumptions_ch.json with its official source.
"""
from __future__ import annotations

import numpy as np

BANDS = ((25, "payroll_bvg_credit_25"), (35, "payroll_bvg_credit_35"),
         (45, "payroll_bvg_credit_45"), (55, "payroll_bvg_credit_55"))
RETIRE = 65


def bvg_credit_rate(age, A: dict) -> np.ndarray:
    """Total age-credit rate (employee + employer) for an age (scalar or array, years)."""
    age = np.asarray(age, dtype=float)
    rate = np.zeros_like(age)
    for start, key in BANDS:
        rate = np.where(age >= start, A[key], rate)
    return np.where(age >= RETIRE, 0.0, rate)


def payroll(gross_month, age_years, A: dict) -> dict[str, np.ndarray]:
    """Monthly employee deductions and net salary for gross monthly salaries (arrays).

    Returns arrays: gross, ahv_iv_eo, alv, nbu, social (= ahv_iv_eo + alv + nbu),
    bvg_employee, bvg_employer, net (= gross - social - bvg_employee)."""
    g = np.maximum(np.asarray(gross_month, dtype=float), 0.0)
    annual = 12.0 * g
    insured = np.minimum(g, A["payroll_alv_cap"] / 12.0)
    ahv = A["payroll_ahv_iv_eo_rate"] * g
    alv = A["payroll_alv_rate"] * insured
    nbu = A["payroll_nbu_rate"] * insured
    coordinated = np.clip(np.minimum(annual, A["payroll_bvg_max"]) - A["payroll_bvg_coord"],
                          A["payroll_bvg_min_coord"], A["payroll_bvg_max"] - A["payroll_bvg_coord"])
    coordinated = np.where(annual >= A["payroll_bvg_entry"], coordinated, 0.0)
    credit = bvg_credit_rate(age_years, A) * coordinated / 12.0
    employee = A["payroll_bvg_employee_share"] * credit
    social = ahv + alv + nbu
    return {"gross": g, "ahv_iv_eo": ahv, "alv": alv, "nbu": nbu, "social": social,
            "bvg_employee": employee, "bvg_employer": credit - employee, "net": g - social - employee}


def payslip(gross_month: float, age: float, A: dict) -> dict[str, float]:
    """One month's payslip as plain numbers (for the API and tests)."""
    p = payroll(np.array([gross_month]), np.array([age]), A)
    return {k: round(float(v[0]), 2) for k, v in p.items()}
