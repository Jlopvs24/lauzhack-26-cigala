"""Weather = things the user does not choose, applied as stress on a node.

Each weather event is ``{"type": ..., "start_month": m, ...params}``. Events
change the external conditions month by month; they apply to the
deterministic path AND to every Monte Carlo path.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import month_int, num

CATALOG = {
    "recession": {
        "label": "Recession",
        "description": "Jobs are harder to keep and markets fall: job-loss probability x3, no real wage growth, "
                       "portfolio returns 15 points/year lower during the window.",
        "defaults": {"start_month": 12, "duration_months": 18, "job_loss_multiplier": 3.0, "return_shift": -0.15},
    },
    "inflation": {
        "label": "High inflation",
        "description": "Prices rise faster than planned while wages keep their usual pace: purchasing power drops.",
        "defaults": {"start_month": 0, "duration_months": 24, "annual_rate": 0.05},
    },
    "market_crash": {
        "label": "Market crash",
        "description": "Invested savings lose a share of their value in one month, then markets behave as usual.",
        "defaults": {"start_month": 12, "drop": 0.30},
    },
    "chf_strengthens": {
        "label": "Swiss franc strengthens",
        "description": "EURCHF falls by a share from the start month: what is earned or spent in EUR is worth fewer francs.",
        "defaults": {"start_month": 0, "duration_months": 1200, "change": -0.10},
    },
    "chf_weakens": {
        "label": "Swiss franc weakens",
        "description": "EURCHF rises by a share from the start month: what is earned or spent in EUR is worth more francs.",
        "defaults": {"start_month": 0, "duration_months": 1200, "change": 0.10},
    },
    "job_loss": {
        "label": "Job loss",
        "description": "Income stops for a few months; unemployment insurance replaces part of it "
                       "(see assumption AS-unemployment-replacement).",
        "defaults": {"start_month": 12, "duration_months": 6},
    },
}


def weather_catalog() -> list[dict]:
    return [{"type": k, **v} for k, v in CATALOG.items()]


@dataclass
class WeatherArrays:
    inflation_override: np.ndarray   # (H,) annual rate or NaN
    real_wage_override: np.ndarray   # (H,) annual rate or NaN
    return_shift: np.ndarray         # (H,) added to annual expected return
    return_shock: np.ndarray         # (H,) multiplicative one-off factor on investments (1 = none)
    job_loss_multiplier: np.ndarray  # (H,)
    forced_unemployment: np.ndarray  # (H,) bool
    applied: list[dict]
    fx_factor: np.ndarray | None = None  # (H,) multiplies EURCHF (#48 item 5), 1 = assumption


def build_weather(events: list[dict] | None, H: int) -> WeatherArrays:
    w = WeatherArrays(
        inflation_override=np.full(H, np.nan),
        real_wage_override=np.full(H, np.nan),
        return_shift=np.zeros(H),
        return_shock=np.ones(H),
        job_loss_multiplier=np.ones(H),
        forced_unemployment=np.zeros(H, dtype=bool),
        applied=[],
        fx_factor=np.ones(H),
    )
    for i, ev in enumerate(events or []):
        ev = {"type": ev} if isinstance(ev, str) else ev
        typ = ev.get("type")
        typ = "inflation" if typ == "high_inflation" else typ
        if typ not in CATALOG:
            raise ValueError(f"weather[{i}].type must be one of {list(CATALOG)}")
        p = {**CATALOG[typ]["defaults"], **{k: v for k, v in ev.items() if k != "type"}}
        start = month_int(p["start_month"], f"weather[{i}].start_month", H)
        end = min(H, start + int(num(p.get("duration_months", 1), f"weather[{i}].duration_months", minimum=1)))
        win = slice(start, end)
        if typ == "recession":
            w.job_loss_multiplier[win] *= num(p["job_loss_multiplier"], "job_loss_multiplier", minimum=0)
            w.real_wage_override[win] = 0.0
            w.return_shift[win] += num(p["return_shift"], "return_shift")
        elif typ == "inflation":
            w.inflation_override[win] = num(p["annual_rate"], "annual_rate")
        elif typ == "market_crash":
            drop = num(p["drop"], "drop", minimum=0)
            if drop >= 1:
                raise ValueError("market_crash.drop must be < 1")
            w.return_shock[start] *= 1 - drop
            end = start + 1
        elif typ == "job_loss":
            w.forced_unemployment[win] = True
        elif typ in ("chf_strengthens", "chf_weakens"):
            ch = num(p["change"], "change")
            if ch <= -1:
                raise ValueError(f"{typ}.change must be > -1")
            w.fx_factor[win] *= 1.0 + ch
        w.applied.append({"type": typ, "label": CATALOG[typ]["label"], **p, "end_month": end})
    return w
