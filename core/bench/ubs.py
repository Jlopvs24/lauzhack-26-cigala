"""Read the UBS synthetic data (vendor/ubs-kit/Data, private and gitignored).

Standard library + numpy only, like the engine. Fetch the kit with
``bash scripts/fetch_ubs_kit.sh`` (needs an account UBS granted access to).
"""
from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "vendor" / "ubs-kit" / "Data"


def available(data: Path = DATA) -> bool:
    return (data / "synthetic-profiles.csv").exists()


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=2)
def load(data: Path = DATA) -> dict:
    """Profiles, accounts, assets, liabilities, goals, scenario assumptions, life events and
    the monthly cash ledger, indexed by profile_id. Transactions are aggregated per
    (profile, month, category) because the raw file has ~550k rows."""
    if not available(data):
        raise FileNotFoundError(f"UBS kit not found in {data}; run bash scripts/fetch_ubs_kit.sh")
    out: dict = {"profiles": {r["profile_id"]: r for r in _rows(data / "synthetic-profiles.csv")}}
    for key, fname in (("assets", "synthetic-assets.csv"), ("liabilities", "synthetic-liabilities.csv"),
                       ("goals", "synthetic-goals.csv"), ("scenario_assumptions", "scenario-assumptions.csv"),
                       ("life_events", "life-events.csv")):
        group = defaultdict(list)
        for r in _rows(data / fname):
            group[r["profile_id"]].append(r)
        out[key] = dict(group)
    ledger = defaultdict(list)
    for r in _rows(data / "synthetic-cash-balances.csv"):
        ledger[r["profile_id"]].append({"month": r["month"], "opening": _num(r["opening_cash_chf"]),
                                        "net": _num(r["net_transactions_chf"]), "closing": _num(r["closing_cash_chf"]),
                                        "status": r["status"]})
    out["ledger"] = {k: sorted(v, key=lambda x: x["month"]) for k, v in ledger.items()}
    out["flows"] = _transactions(data)
    out["catalog"] = _rows(data / "scenario-catalog.csv")
    return out


def _transactions(data: Path) -> dict:
    """{profile_id: {month: {category: amount}}} from the zipped transaction file."""
    z = zipfile.ZipFile(data / "synthetic-transactions.zip")
    name = next(n for n in z.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX"))
    flows: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    with z.open(name) as raw:
        for r in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8")):
            flows[r["profile_id"]][r["date"][:7]][r["category"]] += float(r["amount_chf"])
    return {p: {m: dict(c) for m, c in months.items()} for p, months in flows.items()}
