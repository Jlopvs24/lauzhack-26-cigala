"""Income tax by place and household (#48 item 3).

Effective-rate tables come from the official ESTV tax calculator (federal + cantonal + communal
income tax, tax year 2026, no church tax), stored in core/data/tax_ch_2026.json and rebuilt with
``python -m core.bench.fetch_estv``. A table is keyed by the annual **net** salary (payslip net,
before income tax), the engine's ``net_before_tax`` income, and maps it to tax / net.

Residence: ``city`` if we have its table, else the main city of ``canton``, else Lausanne (and the
result says so: ``fallback: true``). Household: ``single`` (also ``shared_housing``), ``couple``
(married, one earner), ``family`` (married, one earner, two children). Abroad: a flat effective
rate, the assumption ``tax_abroad_rate`` (a modelling choice, not verified).
"""
from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "tax_ch_2026.json"
CANTON_CITY = {"VD": "Lausanne", "ZH": "Zurich", "GE": "Geneva", "BE": "Bern", "BS": "Basel",
               "FR": "Fribourg", "NE": "Neuchatel", "SG": "St Gallen", "TI": "Lugano", "LU": "Lucerne"}
HOUSEHOLDS = {"single": "single", "shared_housing": "single", "couple": "couple", "family": "family"}
ALIASES = {"zurich": "Zurich", "zuerich": "Zurich", "geneve": "Geneva", "genf": "Geneva", "geneva": "Geneva",
           "lausanne": "Lausanne", "bern": "Bern", "berne": "Bern", "biel": "Biel", "bienne": "Biel",
           "biel/bienne": "Biel", "basel": "Basel", "bale": "Basel", "fribourg": "Fribourg", "freiburg": "Fribourg",
           "neuchatel": "Neuchatel", "st gallen": "St Gallen", "st. gallen": "St Gallen", "sankt gallen": "St Gallen",
           "saint-gall": "St Gallen", "lugano": "Lugano", "lucerne": "Lucerne", "luzern": "Lucerne",
           "winterthur": "Winterthur"}
DEFAULT_CITY = "Lausanne"
ABROAD = "abroad"


def _key(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().strip().lower()
    return " ".join(s.split())


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def household(value: str | None) -> str:
    if value is None or value == "":
        return "single"
    if value not in HOUSEHOLDS:
        raise ValueError(f"household_type must be one of {tuple(HOUSEHOLDS)}, got {value!r}")
    return HOUSEHOLDS[value]


def resolve(city: str | None = None, canton: str | None = None, household_type: str | None = None,
            country: str | None = None) -> dict:
    """Where and as what the income is taxed: ``{city, canton, household, country, source, fallback}``."""
    return dict(_resolve(city, canton, household_type, country))


@lru_cache(maxsize=512)
def _resolve(city, canton, household_type, country) -> tuple:
    return tuple(_resolve_uncached(city, canton, household_type, country).items())


def _resolve_uncached(city, canton, household_type, country) -> dict:
    hh = household(household_type)
    if country and _key(country) not in ("ch", "switzerland", "schweiz", "suisse"):
        return {"city": None, "canton": None, "household": hh, "country": str(country),
                "source": "assumption:tax_abroad_rate", "fallback": False}
    d = data()
    name = ALIASES.get(_key(city)) if city else None
    if name and name in d["locations"]:
        how = "city"
    elif canton and str(canton).upper() in CANTON_CITY:
        name, how = CANTON_CITY[str(canton).upper()], "canton"
    else:
        name, how = DEFAULT_CITY, "default"
    return {"city": name, "canton": d["locations"][name]["canton"], "household": hh, "country": "CH",
            "source": f"ESTV {d['tax_year']}", "matched": how, "fallback": how == "default"}


@lru_cache(maxsize=64)
def _swiss_table(city: str, hh: str) -> tuple[tuple[float, float], ...]:
    pts = data()["tables"][f"{city}|{hh}"]
    rows = [(0.0, 0.0)] + [(float(n), (t / n) if n > 0 else 0.0) for n, t in pts]
    return tuple(rows)


def table(res: dict, abroad_rate: float = 0.0) -> list[list[float]]:
    """``[[annual net salary, effective rate], ...]`` for a resolved residence."""
    if res.get("country") not in (None, "CH"):
        return [[0.0, float(abroad_rate)], [1.0, float(abroad_rate)]]
    return [list(p) for p in _swiss_table(res["city"], res["household"])]
