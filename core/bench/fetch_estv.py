"""Rebuild core/data/tax_ch_2026.json from the official ESTV tax calculator (#48 item 3).

    python -m core.bench.fetch_estv [--year 2026]

Uses the public API behind https://swisstaxcalculator.estv.admin.ch (the same calls the web
calculator makes): for each city and household it asks the federal + cantonal + communal income
tax of an employee at a grid of gross salaries. The calculator applies the standard Swiss payroll
deductions and the standard tax deductions; we keep its payslip net salary (``NetIncome``, after
social contributions and BVG, before income tax: our ``net_before_tax``) and the total tax. The
engine keys the tables on that net salary, so the calculator's own payroll defaults do not leak
into our payroll layer. ~540 requests, a short pause between them.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

API = "https://swisstaxcalculator.estv.admin.ch/delegate/ost-integration/v1/lg-proxy/operation/c3b67379_ESTV/"
OUT = Path(__file__).resolve().parent.parent / "data"
# cities of the UBS synthetic profiles (canton -> its main city is in core/tax.py), by postcode
CITIES = {"Lausanne": "1000", "Zurich": "8001", "Geneva": "1204", "Bern": "3011", "Biel": "2502",
          "Basel": "4001", "Fribourg": "1700", "Neuchatel": "2000", "St Gallen": "9000",
          "Lugano": "6900", "Lucerne": "6003", "Winterthur": "8400"}
GROSS = [15000, 20000, 25000, 30000, 40000, 50000, 60000, 70000, 80000, 100000, 120000, 150000,
         200000, 250000, 300000]
# Relationship 1 = single, 2 = married; couples are single-earner (Revenue2 = 0)
HOUSEHOLDS = {"single": (1, []), "couple": (2, []), "family": (2, [{"Age": 6}, {"Age": 9}])}
NO_CONFESSION = 4
EMPLOYED = 1


def _post(op: str, body: dict) -> dict:
    req = urllib.request.Request(API + op, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())["response"]
        except Exception:  # transient (the calculator is sometimes being updated)
            time.sleep(2 + 3 * i)
    raise RuntimeError(f"ESTV {op} failed")


def request(year: int, location_id: int, household: str, gross: float) -> dict:
    rel, kids = HOUSEHOLDS[household]
    return {"SimKey": None, "TaxYear": year, "TaxLocationID": location_id, "Relationship": rel,
            "Confession1": NO_CONFESSION, "Children": kids, "Age1": 30, "RevenueType1": EMPLOYED, "Revenue1": gross,
            "Fortune": 0, "Confession2": NO_CONFESSION if rel == 2 else 0, "Age2": 30 if rel == 2 else 0,
            "RevenueType2": 0, "Revenue2": 0, "Budget": []}


def fetch(year: int) -> dict:
    out = {"tax_year": year, "retrieved": time.strftime("%Y-%m-%d"), "source": API + "API_calculateDetailedTaxes",
           "calculator": "https://swisstaxcalculator.estv.admin.ch",
           "request_template": request(year, 0, "single", 0) | {"TaxLocationID": "per city", "Revenue1": "gross salary grid"},
           "settings": "employee aged 30, no church tax, no wealth; couple/family = married, one earner; family = 2 children (6, 9)",
           "point_unit": "[annual net salary CHF (payslip net, before income tax), total income tax CHF (federal + cantonal + communal + personal)]",
           "locations": {}, "tables": {}}
    for city, postcode in CITIES.items():
        loc = _post("API_searchLocation", {"Search": postcode})[0]
        out["locations"][city] = {"postcode": postcode, "canton": loc["Canton"], "bfs_id": loc["BfsID"],
                                  "tax_location_id": loc["TaxLocationID"]}
        for hh in HOUSEHOLDS:
            pts = []
            for g in GROSS:
                r = _post("API_calculateDetailedTaxes", request(year, loc["TaxLocationID"], hh, g))
                pts.append([r["IncomeP1"]["NetIncome"], r["TotalNetTax"]])
                time.sleep(0.15)
            out["tables"][f"{city}|{hh}"] = pts
            print(city, hh, pts[::5], flush=True)
    return out


def write(d: dict, path: Path) -> None:
    """One table per line, so diffs stay readable."""
    head = {k: v for k, v in d.items() if k != "tables"}
    lines = json.dumps(head, ensure_ascii=False, indent=1)[:-2] + ',\n "tables": {\n'
    rows = [f'  {json.dumps(k)}: {json.dumps(v)}' for k, v in d["tables"].items()]
    path.write_text(lines + ",\n".join(rows) + "\n }\n}\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    a = ap.parse_args()
    write(fetch(a.year), OUT / f"tax_ch_{a.year}.json")
