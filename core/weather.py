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



# These are conditional stress choices, not estimates or forecasts. Sources provide
# context for the channels and scale; the exact scenario magnitudes are not verified.
SOURCES = {
    "inflation": "https://dam-api.bfs.admin.ch/hub/api/dam/assets/30525764/master",
    "markets": "https://www.pictet.com/content/dam/www/documents/publications/shares-and-bonds-in-switzerland/2025/PWM_Performance-Swiss-shares-and-bonds-EN.pdf",
    "macro": "https://www.snb.ch/en/publications/communication/summaries/zus_20251023",
    "fx": "https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.CHF.EUR.SP00.A",
}

QUALITATIVE = {
    "scenario": {
        "pessimistic": ("Pessimistic", "Prices rise faster, pay grows less and markets face headwinds.",
                        {"inflation_override": 0.03, "real_wage_override": 0.0, "return_shift": -0.05, "job_loss_multiplier": 2.0}),
        "neutral": ("Neutral", "Keep the current assumptions without a macro shift.", {}),
        "optimistic": ("Optimistic", "Prices rise slowly, pay grows faster and markets have a tailwind.",
                       {"inflation_override": 0.005, "real_wage_override": 0.02, "return_shift": 0.03, "job_loss_multiplier": 0.5}),
    },
    "inflation": {
        "high": ("High inflation", "Prices rise faster while pay keeps its usual pace.", {"inflation_override": 0.03}),
        "low": ("Low inflation", "Prices stay level while pay keeps its usual pace.", {"inflation_override": 0.0}),
    },
    "fx": {
        "chf_strong": ("Strong franc", "Income and costs in euros are worth fewer francs.", {"fx_factor": 0.9}),
        "chf_weak": ("Weak franc", "Income and costs in euros are worth more francs.", {"fx_factor": 1.1}),
    },
    "markets": {
        "crash": ("Market crash", "Invested savings fall at the start, then returns follow the usual assumptions.", {"return_shock": 0.7, "return_shift": 0.0}),
        "boom": ("Market boom", "Invested savings earn more during the scenario.", {"return_shift": 0.05}),
    },
    "jobs": {
        "weak": ("Weak job market", "Real pay stops growing and simulated job losses are more frequent.",
                 {"real_wage_override": 0.0, "job_loss_multiplier": 2.0}),
        "strong": ("Strong job market", "Real pay grows faster and simulated job losses are less frequent.",
                   {"real_wage_override": 0.02, "job_loss_multiplier": 0.5}),
    },
    "rates": {
        "up": ("Rates rise", "Cash savings earn more; existing fixed-rate loans keep their terms.", {"cash_rate_shift": 0.01}),
        "down": ("Rates fall", "Cash savings earn less, with a floor at zero; fixed-rate loans keep their terms.", {"cash_rate_shift": -0.01}),
    },
}



ASSUMPTION_LABELS = {
    "inflation_override": ("Annual price growth", 100, "%"),
    "real_wage_override": ("Annual real wage growth", 100, "%"),
    "return_shift": ("Annual portfolio return change", 100, "percentage points"),
    "job_loss_multiplier": ("Simulated job-loss hazard", 1, "times the base assumption"),
    "fx_factor": ("EURCHF during the scenario", 1, "times the base rate"),
    "return_shock": ("Invested balance after the initial shock", 1, "times the opening invested balance"),
    "cash_rate_shift": ("Annual cash-savings rate change", 100, "percentage points, floored at zero"),
}

def qualitative_option(typ: str, level: str) -> dict:
    label, description, assumptions = QUALITATIVE[typ][level]
    source_keys = ["macro", "inflation", "markets"] if typ == "scenario" else [typ if typ in SOURCES else "macro"]
    notes = [{"label": ASSUMPTION_LABELS[k][0], "value": round(v * ASSUMPTION_LABELS[k][1], 4),
              "unit": ASSUMPTION_LABELS[k][2]} for k, v in assumptions.items()]
    return {"id": f"{typ}:{level}", "type": typ, "level": level, "label": label, "description": description,
            "defaults": {"start_month": 0, "duration_months": 1200 if typ == "fx" else 24},
            "assumptions": notes, "verified": False,
            "source": "Team-defined conditional scenario; sources provide context, not a calibrated joint forecast.",
            "sources": [SOURCES[k] for k in source_keys]}


def weather_catalog() -> list[dict]:
    return ([{"type": k, **v} for k, v in CATALOG.items()] +
            [qualitative_option(typ, level) for typ, levels in QUALITATIVE.items() for level in levels])


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
    cash_rate_shift: np.ndarray | None = None  # (H,) savings-rate shift; fixed loans are unchanged


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
        cash_rate_shift=np.zeros(H),
    )
    events = [{"type": ev} if isinstance(ev, str) else ev for ev in events or []]
    if any(not isinstance(ev, dict) for ev in events):
        raise ValueError("weather events must be objects or known type strings")
    seen = set()
    # Explicit factors override the macro perspective, independent of request order.
    ordered = sorted(enumerate(events), key=lambda pair: pair[1].get("type") != "scenario")
    for i, ev in ordered:
        typ = ev.get("type")
        if not isinstance(typ, str):
            raise ValueError(f"weather[{i}].type must be a string")
        typ = "inflation" if typ == "high_inflation" else typ
        if "level" in ev or typ in QUALITATIVE and typ != "inflation":
            level = ev.get("level")
            if typ not in QUALITATIVE or not isinstance(level, str) or level not in QUALITATIVE[typ]:
                raise ValueError(f"weather[{i}] has an unknown qualitative type or level")
            if typ in seen:
                raise ValueError(f"weather has more than one qualitative {typ} factor")
            seen.add(typ)
            if set(ev) - {"type", "level", "start_month", "duration_months"}:
                raise ValueError("qualitative weather accepts only type, level and an optional time window")
            option = qualitative_option(typ, level)
            p = {**option["defaults"], **ev}
            start = month_int(p["start_month"], f"weather[{i}].start_month", H)
            duration = num(p["duration_months"], f"weather[{i}].duration_months", minimum=1)
            if not duration.is_integer():
                raise ValueError("weather duration must be an integer")
            duration = int(duration)
            end = min(H, start + duration)
            for field, value in QUALITATIVE[typ][level][2].items():
                getattr(w, field)[start:start + 1 if field == "return_shock" else end] = value
            w.applied.append({**option, **p, "end_month": end})
            continue
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
