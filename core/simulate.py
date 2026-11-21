"""Public entry point: one node -> one SimulationResult (contract v1)."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import numpy as np

from . import analysis as an
from .assumptions import AssumptionSet, build_assumptions
from .engine import FLOW_KEYS, run, run_batch
from .models import Profile, parse_interventions
from .schedule import build_schedule
from .weather import build_weather

DEFAULT_SEED = 42
DEFAULT_PATHS = 1000
SENSITIVITY_PATHS = 100
ENGINE_VERSION = "core-1.0"


def _prepare(profile: Profile, interventions: list[dict], aset: AssumptionSet, weather: list[dict] | None):
    A = aset.values()
    ivs = parse_interventions(interventions, A, profile.horizon_months)
    sched = build_schedule(profile, ivs)
    w = build_weather(weather, profile.horizon_months)
    return A, sched, w


def _run(profile, sched, A, aset, w, **kw):
    return run(sched, profile.cash, profile.investments, A, aset.tax_table(), w, **kw)


def simulate_node(profile: dict | Profile, interventions: list[dict] | None = None, *,
                  assumptions: AssumptionSet | None = None, extra_assumptions: list[dict] | None = None,
                  overrides: dict[str, Any] | None = None, weather: list[dict] | None = None,
                  node_id: str = "0", n_paths: int = DEFAULT_PATHS, seed: int = DEFAULT_SEED,
                  sensitivity: bool = False, include_flows: bool = True) -> dict:
    """Simulate a profile under a list of interventions (already flattened root -> node).

    Returns a JSON-serialisable SimulationResult. Every number the UI or the
    agent shows must come from here.
    """
    t0 = time.perf_counter()
    prof = profile if isinstance(profile, Profile) else Profile.from_dict(profile)
    aset = assumptions or build_assumptions(extra_assumptions or [], overrides)
    if assumptions is not None and overrides:
        aset = assumptions.with_overrides(overrides)
    interventions = interventions or []
    A, sched, w = _prepare(prof, interventions, aset, weather)

    det = _run(prof, sched, A, aset, w, stochastic=False, keep_flows=True)
    mc = _run(prof, sched, A, aset, w, n_paths=n_paths, seed=seed, stochastic=True)

    goals = an.evaluate_goals(prof, det, mc)
    f = {k: v[0] for k, v in det.flows.items()}
    cash_d = det.cash[0]
    real_nw = det.net_worth[0] / det.cpi[0]
    min_k = int(np.argmin(cash_d[1:]))
    final_nw_mc = mc.net_worth[:, -1]
    min_cash_mc = mc.cash[:, 1:].min(axis=1)
    used = [a for a in aset.to_list()]
    metrics = {
        "final_cash": an.r2(cash_d[-1]),
        "final_net_worth": an.r2(det.net_worth[0, -1]),
        "final_net_worth_real": an.r2(real_nw[-1]),
        "final_net_worth_p10": an.r2(np.percentile(final_nw_mc, 10)),
        "final_net_worth_p50": an.r2(np.percentile(final_nw_mc, 50)),
        "final_net_worth_p90": an.r2(np.percentile(final_nw_mc, 90)),
        "min_cash": an.r2(cash_d[1:].min()),
        "min_cash_month": min_k,
        "first_negative_month": an.first_negative(cash_d),
        "shortfall_probability": round(float(np.mean(min_cash_mc < -an.TOL)), 3),
        "min_cash_p10": an.r2(np.percentile(min_cash_mc, 10)),
        "total_income": an.r2(f["income"].sum()),
        "total_income_tax": an.r2(f["income_tax"].sum()),
        "total_living_expenses": an.r2(f["living_expenses"].sum()),
        "total_one_off_costs": an.r2(f["one_off_cost"].sum()),
        "total_debt_interest": an.r2(f["debt_interest"].sum()),
        "total_investment_return": an.r2(f["investment_return"].sum()),
        "final_debt": an.r2(det.debt[-1]),
        "avg_unemployed_months": round(float(mc.unemployed_months.mean()), 2),
        "goal_probability": {g["name"]: g["probability"] for g in goals},
    }
    hl = an.health(det, mc, goals, A)
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

    result = {
        "node_id": node_id,
        "engine_version": ENGINE_VERSION,
        "currency": "CHF",
        "as_of": prof.as_of.isoformat(),
        "seed": seed,
        "n_paths": n_paths,
        "horizon_months": prof.horizon_months,
        "deterministic": deterministic,
        "bands": {"cash": an.bands(mc.cash), "net_worth": an.bands(mc.net_worth)},
        "metrics": metrics,
        "goals": goals,
        "health": hl,
        "sensitivity": sensitivity_analysis(prof, interventions, aset, weather, seed) if sensitivity else None,
        "checks": an.checks(det, mc, used),
        "events": sched.events,
        "debts": det.debt_detail.per_liability,
        "weather": w.applied,
        "assumptions_used": [{"id": a["id"], "value": a["value"], **({"user_edited": True} if a.get("user_edited") else {})}
                             for a in used],
        "trace_id": trace_id(prof.raw, interventions, used, weather, n_paths, seed),
    }
    result["timing_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return result


def sensitivity_analysis(profile: Profile, interventions: list[dict], aset: AssumptionSet,
                         weather: list[dict] | None, seed: int = DEFAULT_SEED,
                         n_paths: int = SENSITIVITY_PATHS) -> list[dict]:
    """Tornado: move each assumption that declares a ``range`` to its low and
    high value, all else fixed, and measure the change in the MEAN final net
    worth over ``n_paths`` Monte Carlo paths with common random numbers (same
    seed), so the comparison is not noise. All variants run in ONE batched pass.
    Sorted by swing, largest first."""
    variants: list[tuple[dict | None, str]] = [(None, "base")]
    for a in aset.to_list():
        if a.get("range"):
            variants += [(a, "low"), (a, "high")]
    scheds, As = [], []
    w = None
    for a, side in variants:
        va = aset if a is None else aset.with_overrides({a["id"]: a["range"][0 if side == "low" else 1]})
        A, sched, w = _prepare(profile, interventions, va, weather)
        scheds.append(sched)
        As.append(A)
    # one vectorised pass: every variant reuses the same random draws (common random numbers)
    out = run_batch(scheds, As, profile.cash, profile.investments, aset.tax_table(), w,
                    n_paths=n_paths, seed=seed, stochastic=True)
    final = out.net_worth[:, -1].reshape(len(variants), n_paths).mean(axis=1)
    short = (out.cash[:, 1:].min(axis=1) < -an.TOL).reshape(len(variants), n_paths).mean(axis=1)
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
            "shortfall_probability_low": round(float(short[i]), 3),
            "shortfall_probability_high": round(float(short[i + 1]), 3),
        })
    rows = [r for r in rows if r["delta_final_net_worth"] >= 1.0]  # drop assumptions this node does not use
    rows.sort(key=lambda r: r["delta_final_net_worth"], reverse=True)
    for r in rows:
        r["base_final_net_worth"] = an.r2(base_nw)
    return rows


def trace_id(*parts) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str).encode()
    return "sim-" + hashlib.sha1(blob).hexdigest()[:12]
