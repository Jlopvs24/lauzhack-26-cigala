"""Calibration / benchmark harness for the engine (#42).

Three uses, in order of importance (Juan's direction: correctness first, never fit the
model to synthetic data):
1. ``ledger_consistency``: the UBS ledgers' own identities (opening + net = closing,
   months chain, transactions sum to the monthly net). Checks the data and our reading of it.
2. ``replay``: every UBS profile run through OUR engine for its 24 ledger months, in the
   cash-only world (sanity: same budget -> same cash) and in our Swiss default world
   (shows what we add on top of their ledger: income tax, inflation, wage growth).
   ``implied_parameters``: what the synthetic generator implies (wage growth, cost growth,
   surprise expenses) next to our assumptions.
3. ``score``: a parameter set against PUBLIC Swiss targets (targets.json; only the ones
   marked verified count by default). ``search`` runs a grid over a parameter set.

    python -m core.bench            # full report (needs vendor/ubs-kit)
    python -m core.bench --json     # same, as JSON
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path
from statistics import mean, median

import numpy as np

from ..assumptions import build_assumptions, zero_world_assumptions
from ..engine import run
from ..models import Profile, parse_interventions
from ..schedule import build_schedule
from ..weather import build_weather
from . import ubs

HERE = Path(__file__).resolve().parent
IRREGULAR = ("unexpected_expense", "travel", "education")
INCOME_CATS = ("salary_or_support", "annual_bonus")


# ---------------------------------------------------------------- 1. ledger consistency
def ledger_consistency(kit: dict | None = None) -> dict:
    kit = kit or ubs.load()
    worst = {"identity": 0.0, "chain": 0.0, "transactions": 0.0}
    bad = {k: 0 for k in worst}
    months = 0
    for pid, rows in kit["ledger"].items():
        flows = kit["flows"].get(pid, {})
        for i, r in enumerate(rows):
            months += 1
            e = abs(r["opening"] + r["net"] - r["closing"])
            worst["identity"] = max(worst["identity"], e); bad["identity"] += e > 0.01
            if i:
                e = abs(rows[i - 1]["closing"] - r["opening"])
                worst["chain"] = max(worst["chain"], e); bad["chain"] += e > 0.01
            e = abs(sum(flows.get(r["month"], {}).values()) - r["net"])
            worst["transactions"] = max(worst["transactions"], e); bad["transactions"] += e > 0.01
    return {"profiles": len(kit["ledger"]), "months": months, "passed": not any(bad.values()),
            "violations": bad, "max_abs_error_chf": {k: round(v, 4) for k, v in worst.items()}}


# ---------------------------------------------------------------- 2a. implied parameters
def _by_year(flows: dict, cats) -> tuple[float, float]:
    y1 = [sum(c.get(k, 0.0) for k in cats) for m, c in flows.items() if m.startswith("2025")]
    y2 = [sum(c.get(k, 0.0) for k in cats) for m, c in flows.items() if m.startswith("2026")]
    return (sum(y1), sum(y2))


def implied_parameters(kit: dict | None = None, overrides: dict | None = None) -> dict:
    """What the synthetic generator implies, next to our assumption values."""
    kit = kit or ubs.load()
    A = build_assumptions(overrides=overrides).values()
    inc_g, cost_g, hits, sizes, bonus_share, months = [], [], 0, [], [], 0
    recurring = None
    for pid, flows in kit["flows"].items():
        a, b = _by_year(flows, ("salary_or_support",))
        if a > 0:
            inc_g.append(b / a - 1)
        cats = set().union(*flows.values()) - set(INCOME_CATS) - set(IRREGULAR) - {"housing_rent"}
        recurring = cats if recurring is None else recurring | cats
        a, b = _by_year(flows, tuple(cats))
        if a < 0:
            cost_g.append(b / a - 1)
        for c in flows.values():
            months += 1
            if c.get("unexpected_expense", 0.0) < 0:
                hits += 1
                sizes.append(-c["unexpected_expense"])
        bonus = sum(c.get("annual_bonus", 0.0) for c in flows.values())
        sal = sum(c.get("salary_or_support", 0.0) for c in flows.values())
        if sal > 0:
            bonus_share.append(bonus / sal)
    nominal_wage = A["inflation_mean"] + A["real_wage_growth"]
    rows = [
        {"quantity": "salary growth year 2 vs year 1", "ubs_median": round(median(inc_g), 4),
         "ours": round(nominal_wage, 4), "ours_from": "inflation_mean + real_wage_growth"},
        {"quantity": "recurring non-rent spending growth year 2 vs year 1", "ubs_median": round(median(cost_g), 4),
         "ours": A["inflation_mean"], "ours_from": "inflation_mean"},
        {"quantity": "unexpected expenses per year", "ubs_median": round(12 * hits / months, 3),
         "ours": A["unexpected_expense_annual_prob"], "ours_from": "unexpected_expense_annual_prob"},
        {"quantity": "mean unexpected expense (CHF)", "ubs_median": round(mean(sizes), 2) if sizes else None,
         "ours": A["unexpected_expense_mean"], "ours_from": "unexpected_expense_mean"},
        {"quantity": "annual bonus as share of salary", "ubs_median": round(median(bonus_share), 4),
         "ours": 0.0, "ours_from": "not modelled"},
    ]
    return {"rows": rows, "recurring_categories": sorted(recurring or []),
            "note": "Synthetic generator, not Swiss statistics: a sanity reference, never a fitting target."}


# ---------------------------------------------------------------- 2b. replay through our engine
def _budget(pid: str, kit: dict) -> dict:
    """Per-profile monthly budget as the ledger shows it (24-month averages)."""
    flows = kit["flows"].get(pid, {})
    n = max(len(flows), 1)
    tot = lambda cats: sum(sum(c.get(k, 0.0) for k in cats) for c in flows.values()) / n  # noqa: E731
    rent = -tot(("housing_rent",))
    income = tot(INCOME_CATS)
    other = -(sum(sum(v for k, v in c.items() if v < 0 and k != "housing_rent") for c in flows.values()) / n)
    return {"income": income, "rent": rent, "other": other}


def replay(kit: dict | None = None, overrides: dict | None = None, world: str = "zero",
           profiles: list[str] | None = None, income_basis: str = "take_home") -> dict:
    """Run each UBS profile through our engine for its ledger months with its average budget.

    world='zero': cash-only, no inflation/returns/tax/shocks (the starter kit's world): checks
    that the engine turns the same budget into the same cash. world='swiss': our defaults
    (plus ``overrides``): shows the drift our Swiss modelling adds. ``income_basis`` defaults to
    take_home, the basis of imported UBS profiles (#48 item 1); pass net_before_tax to see the
    income tax our engine would add on top of their ledgers."""
    kit = kit or ubs.load()
    aset = build_assumptions(base=zero_world_assumptions(), overrides=overrides) if world == "zero" \
        else build_assumptions(overrides=overrides)
    A = aset.values()
    errs_final, errs_path, scale = [], [], []
    for pid in profiles or sorted(kit["ledger"]):
        rows = kit["ledger"][pid]
        H = len(rows)
        b = _budget(pid, kit)
        prof = Profile.from_dict({"profile_id": pid, "as_of": rows[0]["month"] + "-01", "horizon_months": H,
                                  "cash": max(rows[0]["opening"], 0.0), "monthly_net_income": max(b["income"], 0.0),
                                  "monthly_rent": max(b["rent"], 0.0), "monthly_other_expenses": max(b["other"], 0.0),
                                  "income_basis": income_basis,
                                  # their own tax residence (#48 item 3); only matters for net_before_tax
                                  **{k: kit["profiles"].get(pid, {}).get(k) for k in ("city", "canton", "household_type")}})
        sched = build_schedule(prof, parse_interventions([], A, H), A)
        out = run(sched, prof.cash, 0.0, A, prof.tax_table(aset), build_weather([], H), stochastic=False)
        ours = out.cash[0, 1:]
        theirs = np.array([r["closing"] for r in rows])
        unit = max(b["income"], b["rent"] + b["other"], 1.0)  # one month of the budget
        errs_final.append((ours[-1] - theirs[-1]) / unit)
        errs_path.append(float(np.mean(np.abs(ours - theirs))) / unit)
        scale.append(unit)
    fe = np.array(errs_final)
    return {"world": world, "income_basis": income_basis, "profiles": len(fe), "months": H,
            "final_cash_error_months_of_budget": {"median": round(float(np.median(fe)), 3),
                                                   "p10": round(float(np.percentile(fe, 10)), 3),
                                                   "p90": round(float(np.percentile(fe, 90)), 3)},
            "mean_abs_path_error_months_of_budget": round(float(np.median(errs_path)), 3),
            "how": "Average monthly budget from the ledger, our engine month by month, compared with the ledger's "
                   "closing cash; errors in months of that profile's budget (income or spending, whichever is larger)."}


DRIFT_STEPS = [
    ("our Swiss defaults", {}),
    ("without income tax", {"income_tax_scale": 0}),
    ("... and without inflation", {"income_tax_scale": 0, "inflation_mean": 0, "inflation_sd": 0}),
    ("... and without wage growth", {"income_tax_scale": 0, "inflation_mean": 0, "inflation_sd": 0, "real_wage_growth": 0}),
]


def drift_decomposition(kit: dict | None = None) -> list[dict]:
    """Where the Swiss-world replay departs from the UBS ledgers, switching our additions off one by one."""
    kit = kit or ubs.load()
    rows = []
    for label, ov in DRIFT_STEPS:  # as if their income were before tax: the size of the basis question
        r = replay(kit, overrides=ov or None, world="swiss", income_basis="net_before_tax")
        rows.append({"step": label, "overrides": ov, "final_cash_error_months_of_budget": r["final_cash_error_months_of_budget"]["median"]})
    return rows


def scenario_assumptions_vs_tree(kit: dict | None = None) -> list[dict]:
    """The only scenario parameters in the UBS kit (tuition, study duration) next to our tree."""
    from ..tree import load_tree
    kit = kit or ubs.load()
    tree = {a["id"]: a for a in load_tree()["assumptions"]}
    vals: dict = {}
    for rows in kit["scenario_assumptions"].values():
        for r in rows:
            vals.setdefault(r["parameter"], []).append(float(r["value"]))
    alexia = {r["parameter"]: float(r["value"]) for r in kit["scenario_assumptions"].get("P00001", [])}
    tuition = tree["AS-alexia-master-tuition"]
    out = [{"parameter": "annual_tuition_chf", "ubs_alexia": alexia.get("annual_tuition_chf"),
            "ubs_all_profiles_median": median(vals.get("annual_tuition_chf", [0])),
            "ours": tuition["value"], "ours_range": tuition["range"],
            "note": "ours = starter-kit CHF 2,500/yr (tuition + study costs); UBS synthetic 8,000 is our high end; EPFL invoice 1,560 the low end"},
           {"parameter": "study_duration_years", "ubs_alexia": alexia.get("study_duration_years"),
            "ubs_all_profiles_median": median(vals.get("study_duration_years", [0])),
            "ours": 2, "ours_range": [2, 3], "note": "node 2 = 2 years; 2.1.2 and 2.3 = 3 years"}]
    return out


# ---------------------------------------------------------------- 3. public targets
def load_targets(path: Path = HERE / "targets.json") -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["targets"]


def model_quantity(q: dict, A: dict, tax_table) -> float | None:
    kind = q["kind"]
    if kind == "assumption":
        return A.get(q["param"])
    if kind == "tax_rate_at":  # effective rate of the table at an annual taxable income
        xs = [p[0] for p in tax_table]
        ys = [p[1] for p in tax_table]
        return float(np.interp(q["annual_income_chf"], xs, ys)) * A.get("income_tax_scale", 1.0)
    return None  # quantity not modelled yet (improvement list)


def load_params(path: str | Path) -> tuple[dict, dict]:
    """A parameter file -> (overrides {id: value}, classes {id: 'tunable'|'rule'})."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))["params"]
    return ({k: v["value"] for k, v in raw.items()}, {k: v.get("class", "tunable") for k, v in raw.items()})


def score(overrides: dict | None = None, *, targets: list[dict] | None = None,
          include: tuple[str, ...] = ("verified",)) -> dict:
    """Weighted squared error of a parameter set against public targets, in tolerance units.
    Only targets whose status is in ``include`` count (default: verified ones)."""
    aset = build_assumptions(overrides=overrides)
    A = aset.values()
    parts, total, counted = [], 0.0, 0
    for t in targets or load_targets():
        m = model_quantity(t, A, aset.tax_table())
        row = {"id": t["id"], "status": t["status"], "target": t.get("target"), "model": None if m is None else round(m, 6),
               "tolerance": t.get("tolerance")}
        if m is None or t.get("target") is None:
            row["used"] = False
            row["reason"] = "not modelled yet" if m is None else "target to fill from the source"
        elif t["status"] not in include:
            row["used"] = False
            row["reason"] = f"status {t['status']}"
        else:
            z = (m - t["target"]) / t["tolerance"]
            row.update(used=True, z=round(z, 3), loss=round(t.get("weight", 1.0) * z * z, 4))
            total += row["loss"]
            counted += 1
        parts.append(row)
    return {"loss": round(total, 4), "targets_used": counted, "targets_total": len(parts), "parts": parts}


def search(grid: dict[str, list], *, include: tuple[str, ...] = ("verified",), top: int = 10) -> list[dict]:
    """Exhaustive grid search over assumption ids -> candidate values, ranked by ``score``."""
    keys = list(grid)
    rules = {k for k, c in load_params(HERE / "params.json")[1].items() if c == "rule"}
    if rules & set(keys):
        raise ValueError(f"refusing to search rule parameters {sorted(rules & set(keys))}: source them instead")
    results = []
    for combo in itertools.product(*(grid[k] for k in keys)):
        ov = dict(zip(keys, combo))
        s = score(ov, include=include)
        results.append({"overrides": ov, "loss": s["loss"], "targets_used": s["targets_used"]})
    return sorted(results, key=lambda r: r["loss"])[:top]


def report(kit: dict | None = None, overrides: dict | None = None) -> dict:
    out = {"targets": score(overrides, include=("verified", "to_verify")),
           "targets_verified_only": {k: v for k, v in score(overrides).items() if k != "parts"}}
    if kit is None and not ubs.available():
        out["ubs"] = "UBS kit not found: run bash scripts/fetch_ubs_kit.sh"
        return out
    kit = kit or ubs.load()
    out.update(ledger=ledger_consistency(kit), implied=implied_parameters(kit),
               replay_zero=replay(kit, world="zero"), replay_swiss=replay(kit, world="swiss"),
               drift=drift_decomposition(kit), scenario_assumptions=scenario_assumptions_vs_tree(kit))
    return out
