"""Public entry point: one node -> one SimulationResult (contract v1)."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import numpy as np

from . import analysis as an
from .assumptions import AssumptionSet, build_assumptions
from .engine import FLOW_KEYS, PAYROLL_KEYS, run, run_batch
from .models import Profile, parse_interventions
from .schedule import build_schedule
from .explore import explore_node, levers
from . import plan as pl
from .weather import build_weather

DEFAULT_SEED = 42
DEFAULT_PATHS = 1000
SENSITIVITY_PATHS = 100
ENGINE_VERSION = "core-1.1"


def _prepare(profile: Profile, interventions: list[dict], aset: AssumptionSet, weather: list[dict] | None):
    A = aset.with_node_values(interventions).values()
    ivs = parse_interventions(interventions, A, profile.horizon_months)
    sched = build_schedule(profile, ivs, A)
    w = build_weather(weather, profile.horizon_months)
    return A, sched, w


def _run(profile, sched, A, aset, w, **kw):
    return run(sched, profile.cash, profile.investments, A, profile.tax_table(aset), w, **kw)


def _payroll_summary(prof: Profile, sched, f: dict, A: dict) -> dict | None:
    """Gross -> net view (#48 item 2), or None when no month is paid from a gross salary.

    ``payslip`` is the first paid month at today's prices; ``totals`` are the deterministic
    path's sums (with wage growth, zero while unemployed). The BVG balance is pillar-2 savings
    (opening ``pension_bvg`` assets + employee and employer credits + minimum interest); it is
    locked until retirement and is NOT part of cash, investments or net worth."""
    if sched.gross is None:
        return None
    m = int(np.argmax(sched.gross > 0))
    social = sched.social[m]
    pay = {"month": m, "gross": an.r2(sched.gross[m]), "social_contributions": an.r2(social),
           "bvg_employee": an.r2(sched.bvg_employee[m]), "bvg_employer": an.r2(sched.bvg_employer[m]),
           "net": an.r2(sched.gross[m] - social - sched.bvg_employee[m])}
    g = (1.0 + A["payroll_bvg_interest"]) ** (1.0 / 12.0)
    credits = f["bvg_employee"] + f["bvg_employer"]
    bal = np.empty(len(credits) + 1)
    bal[0] = prof.pension_bvg
    for t, c in enumerate(credits):
        bal[t + 1] = bal[t] * g + c
    return {"payslip": pay,
            "totals": {k: an.r2(f[k].sum()) for k in PAYROLL_KEYS},
            "bvg_balance": an.series(bal), "bvg_balance_final": an.r2(bal[-1]),
            "in_net_worth": False}


def simulate_node(profile: dict | Profile, interventions: list[dict] | None = None, *,
                  assumptions: AssumptionSet | None = None, extra_assumptions: list[dict] | None = None,
                  overrides: dict[str, Any] | None = None, weather: list[dict] | None = None,
                  node_id: str = "0", n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED,
                  sensitivity: bool = False, include_flows: bool = True,
                  uncertainty: bool = False, exploration: bool = False,
                  own_interventions: list[dict] | None = None,
                  comparators: list[dict] | None = None) -> dict:
    """Simulate a profile under a list of interventions (already flattened root -> node).

    Returns a JSON-serialisable SimulationResult. Every number the UI or the
    agent shows must come from here. The primary result is deterministic
    ("if these inputs hold, then..."). ``uncertainty=True`` adds the optional
    Monte Carlo lens (bands, shares of paths). ``exploration=True`` adds the
    deterministic what-would-have-to-be-true analyses (see core/explore.py);
    ``own_interventions`` are this node's own decision (for timing) and
    ``comparators`` are ``[{"node_id", "label", "interventions"}]`` peers (for break-even).
    """
    t0 = time.perf_counter()
    if not isinstance(uncertainty, bool):
        raise ValueError("uncertainty must be a boolean")
    if uncertainty and (isinstance(n_paths, bool) or not isinstance(n_paths, int) or not 1 <= n_paths <= 10000):
        raise ValueError("n_paths must be an integer in 1..10000")
    prof = profile if isinstance(profile, Profile) else Profile.from_dict(profile)
    aset = assumptions or build_assumptions(extra_assumptions or [], overrides)
    if assumptions is not None and overrides:
        aset = assumptions.with_overrides(overrides)
    interventions = interventions or []
    A, sched, w = _prepare(prof, interventions, aset, weather)

    det = _run(prof, sched, A, aset, w, stochastic=False, keep_flows=True)
    mc = _run(prof, sched, A, aset, w, n_paths=n_paths, seed=seed, stochastic=True) if uncertainty else None

    goals = an.evaluate_goals(prof, det, mc)
    f = {k: v[0] for k, v in det.flows.items()}
    cash_d = det.cash[0]
    real_nw = det.net_worth[0] / det.cpi[0]
    min_k = int(np.argmin(cash_d[1:]))
    final_nw_mc = mc.net_worth[:, -1] if mc is not None else None
    min_cash_mc = mc.cash[:, 1:].min(axis=1) if mc is not None else None
    used = aset.with_node_values(interventions).to_list()
    metrics = {
        "final_cash": an.r2(cash_d[-1]),
        "final_net_worth": an.r2(det.net_worth[0, -1]),
        "final_net_worth_real": an.r2(real_nw[-1]),
        "final_net_worth_p10": an.r2(np.percentile(final_nw_mc, 10)) if uncertainty else None,
        "final_net_worth_p50": an.r2(np.percentile(final_nw_mc, 50)) if uncertainty else None,
        "final_net_worth_p90": an.r2(np.percentile(final_nw_mc, 90)) if uncertainty else None,
        "min_cash": an.r2(cash_d[1:].min()),
        "min_cash_month": min_k,
        "first_negative_month": an.first_negative(cash_d),
        "shortfall_probability": round(float(np.mean(min_cash_mc < -an.TOL)), 3) if uncertainty else None,
        "min_cash_p10": an.r2(np.percentile(min_cash_mc, 10)) if uncertainty else None,
        "total_income": an.r2(f["income"].sum()),
        "total_income_tax": an.r2(f["income_tax"].sum()),
        "total_living_expenses": an.r2(f["living_expenses"].sum()),
        "total_one_off_costs": an.r2(f["one_off_cost"].sum()),
        "total_debt_interest": an.r2(f["debt_interest"].sum()),
        "total_investment_return": an.r2(f["investment_return"].sum()),
        "final_debt": an.r2(det.debt[-1]),
        "avg_unemployed_months": round(float(mc.unemployed_months.mean()), 2) if uncertainty else None,
        "goal_probability": {g["name"]: g["probability"] for g in goals} if uncertainty else {},
    }
    resilience = pl.weather_resilience(prof, sched, A, aset, weather, goals)
    hl = an.health(det, mc, goals, A, resilience)
    metrics["liquidity_months"] = hl["components"]["liquidity"]["value"]

    deterministic = {
        "cash": an.series(cash_d),
        "investments": an.series(det.investments[0]),
        "debt": an.series(det.debt),
        "net_worth": an.series(det.net_worth[0]),
        "net_worth_real": an.series(real_nw),
    }
    if include_flows:
        deterministic["flows"] = {k: an.series(f[k]) for k in FLOW_KEYS}
        if sched.gross is not None:
            deterministic["flows"].update({k: an.series(f[k]) for k in PAYROLL_KEYS})

    tornado = sensitivity_analysis(prof, interventions, aset, weather, seed) if (sensitivity or exploration) else None
    result = {
        "node_id": node_id,
        "engine_version": ENGINE_VERSION,
        "currency": "CHF",
        "as_of": prof.as_of.isoformat(),
        "seed": seed,
        "n_paths": n_paths if uncertainty else 0,
        "uncertainty": uncertainty,
        "mode": "deterministic",
        "horizon_months": prof.horizon_months,
        "income_basis": prof.income_basis,
        "payroll": _payroll_summary(prof, sched, f, A),
        "tax_residence": sched.tax_segments,
        "deterministic": deterministic,
        "bands": {key: an.bands(getattr(mc, key)) if uncertainty else {p: [] for p in ("p10", "p50", "p90")}
                  for key in ("cash", "net_worth")},
        "metrics": metrics,
        "goals": goals,
        "health": hl,
        "sensitivity": tornado,
        "checks": an.checks(det, mc if mc is not None else det, used),
        "events": sched.events,
        "debts": det.debt_detail.per_liability,
        "weather": w.applied,
        "assumptions_used": [{"id": a["id"], "value": a["value"], **({"user_edited": True} if a.get("user_edited") else {}),
                              **({"set_by_decision": True} if a.get("set_by_decision") else {})}
                             for a in used],
        "trace_id": trace_id(prof.raw, interventions, used, weather, n_paths if uncertainty else 0,
                             seed if uncertainty else None, uncertainty),
    }
    if exploration:
        result["exploration"] = explore_node(prof, interventions, own_interventions or [], aset, weather,
                                             comparators or [], levers(tornado))
    result["constraints"] = pl.constraints(det, A, goals, aset)
    result["weather_resilience"] = resilience
    result["plan_check"] = pl.plan_check(result["constraints"], resilience, hl, result.get("exploration"))
    result["headline"] = {"slot_a": pl.slot_a(metrics, goals, hl), "slot_b": None, "metric_key": None}
    if not sensitivity:
        result["sensitivity"] = None
    if not uncertainty:
        band_check = next(c for c in result["checks"] if c["name"] == "bands_ordered")
        band_check.update(applicable=False, detail="Not computed: the uncertainty lens is disabled.")
    result["timing_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return result


def sensitivity_analysis(profile: Profile, interventions: list[dict], aset: AssumptionSet,
                         weather: list[dict] | None, seed: int = DEFAULT_SEED,
                         n_paths: int = SENSITIVITY_PATHS) -> list[dict]:
    """Tornado: move each assumption that declares a ``range`` to its low and
    high value, all else fixed, and measure deterministic final net worth.
    All variants run in ONE batched pass, without random draws.
    Sorted by swing, largest first."""
    variants: list[tuple[dict | None, str]] = [(None, "base")]
    for a in aset.with_node_values(interventions).to_list():  # labels/base values as this node sees them
        if a.get("range"):
            variants += [(a, "low"), (a, "high")]
    scheds, As = [], []
    w = None
    for a, side in variants:
        va = aset if a is None else aset.with_overrides({a["id"]: a["range"][0 if side == "low" else 1]})
        A, sched, w = _prepare(profile, interventions, va, weather)
        scheds.append(sched)
        As.append(A)
    # one vectorised deterministic pass over every variant
    out = run_batch(scheds, As, profile.cash, profile.investments, profile.tax_table(aset), w,
                    stochastic=False)
    final = out.net_worth[:, -1]
    short = out.cash[:, 1:].min(axis=1) < -an.TOL
    base_nw = float(final[0])
    rows = []
    for i in range(1, len(variants), 2):
        a = variants[i][0]
        lo_nw, hi_nw = float(final[i]), float(final[i + 1])
        rows.append({
            "assumption_id": a["id"], "label": a.get("label", a["param"]), "unit": a.get("unit", ""),
            "base_value": a["value"], "low_value": a["range"][0], "high_value": a["range"][1],
            "final_net_worth_low": an.r2(lo_nw), "final_net_worth_high": an.r2(hi_nw),
            "delta_final_net_worth": an.r2(abs(hi_nw - lo_nw)),
            "shortfall_probability_low": None, "shortfall_probability_high": None,
            "cash_shortfall_low": bool(short[i]), "cash_shortfall_high": bool(short[i + 1]),
            "basis": "deterministic",
        })
    rows = [r for r in rows if r["delta_final_net_worth"] >= 1.0]  # drop assumptions this node does not use
    rows.sort(key=lambda r: r["delta_final_net_worth"], reverse=True)
    for r in rows:
        r["base_final_net_worth"] = an.r2(base_nw)
    return rows


def trace_id(*parts) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str).encode()
    return "sim-" + hashlib.sha1(blob).hexdigest()[:12]
