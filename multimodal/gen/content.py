"""Build the *content* (and ground truth) of synthetic documents from UBS profiles.

Numbers come from the UBS synthetic profiles (vendor/ubs-kit, never committed).
Everything else (names, employers, addresses, IBANs, line items) is invented here.
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import LANG_BY_CANTON

KIT = Path(__file__).resolve().parents[2] / "vendor" / "ubs-kit" / "Data"

SURNAMES = ["Rochat", "Meier", "Bianchi", "Favre", "Keller", "Rossi", "Dubois", "Huber",
            "Gerber", "Moretti", "Perret", "Brunner", "Ferrari", "Jaquet", "Schmid",
            "Colombo", "Monnier", "Steiner", "Galli", "Vuille", "Baumann", "Conti"]
STREETS = {
    "fr": ["Rue du Marché", "Avenue de la Gare", "Chemin des Vignes", "Rue de Bourg", "Avenue du Léman"],
    "de": ["Bahnhofstrasse", "Seestrasse", "Hauptgasse", "Lindenweg", "Kirchgasse"],
    "it": ["Via Nassa", "Via Cantonale", "Viale Stazione", "Via Pessina", "Corso Elvezia"],
    "en": ["Bahnhofstrasse", "Rue du Lac", "Via Cantonale"],
}
EMPLOYERS = ["Alpenblick Logistik AG", "Léman Services SA", "Helvetic Dataworks GmbH",
             "Ticino Ingegneria SA", "Jura Précision Sàrl", "Rhein Pharma Solutions AG",
             "Café des Arts Sàrl", "Bergsicht Hotels AG", "Lago Verde Retail SA",
             "Campus Bistro Sàrl", "Matterhorn Software AG", "Aare Bau AG"]
PENSION_FUNDS = ["Caisse cantonale de compensation", "Ausgleichskasse des Kantons", "Istituto cantonale delle assicurazioni sociali"]
BANKS = ["Banque Cantonale Fictive", "Alpina Privatbank", "Banca Lago Fittizia", "Swissnova Bank"]
LANDLORDS = ["Gérance Lémanique SA", "Immobilien Rhein AG", "Fondazione Casa Ticino",
             "Régie du Centre Sàrl", "Wohnbau Genossenschaft Linde", "Privé: M. et Mme Cuendet"]
SHOPS = ["Migros", "Coop", "Denner", "Lidl", "Manor", "Aldi Suisse", "Galaxus", "Volg"]
ZIP = {"Lausanne": "1003", "Geneva": "1204", "Lugano": "6900", "Fribourg": "1700", "Basel": "4051",
       "Neuchatel": "2000", "Biel": "2502", "Zurich": "8001", "Bern": "3011", "Lucerne": "6003",
       "St. Gallen": "9000", "Locarno": "6600", "Winterthur": "8400", "Sion": "1950"}


@dataclass
class Person:
    profile_id: str
    first_name: str
    last_name: str
    age: int
    city: str
    canton: str
    lang: str
    employment_status: str
    cash: float
    net_income: float
    rent: float
    street: str
    zip: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass
class DocContent:
    doc_type: str            # payslip | bank_statement | rental_contract
    lang: str
    person: Person
    data: dict               # everything the renderer needs
    truth: dict              # ground-truth fields for the benchmark
    profile_fields: dict = field(default_factory=dict)  # Profile fields this doc supports


def load_people(n: int | None = None, seed: int = 7) -> list[Person]:
    rows = list(csv.DictReader(open(KIT / "synthetic-profiles.csv", encoding="utf-8")))
    rng = random.Random(seed)
    people = []
    for r in rows:
        lang = LANG_BY_CANTON.get(r["canton"], "en")
        people.append(Person(
            profile_id=r["profile_id"], first_name=r["display_name"],
            last_name=rng.choice(SURNAMES), age=int(r["age_at_start"]), city=r["city"],
            canton=r["canton"], lang=lang, employment_status=r["employment_status"],
            cash=round(float(r["opening_cash_chf"]), 2),
            net_income=round(float(r["reference_monthly_net_income_chf"]), 2),
            rent=round(float(r["reference_monthly_rent_chf"]), 2),
            street=f"{rng.choice(STREETS[lang])} {rng.randint(1, 120)}",
            zip=ZIP.get(r["city"], str(rng.randint(1000, 9699))),
        ))
    return people[:n] if n else people


def _r2(x: float) -> float:
    return round(x + 1e-9, 2)


def payslip(p: Person, rng: random.Random, lang: str | None = None) -> DocContent:
    lang = lang or p.lang
    kind = {"retired": "pension", "unemployed": "unemployment"}.get(p.employment_status, "salary")
    net = p.net_income
    lines = []
    if kind == "salary":
        rates = [("ahv", 0.053), ("alv", 0.011), ("nbu", rng.choice([0.0085, 0.011, 0.014]))]
        if p.age >= 25 and net > 1800:
            rates.append(("bvg", rng.choice([0.05, 0.065, 0.075])))
        tot_rate = sum(r for _, r in rates)
        gross = _r2(net / (1 - tot_rate))
        for k, r in rates:
            lines.append((k, _r2(gross * r)))
        # absorb rounding in the last deduction so gross - deductions == net exactly
        diff = _r2(gross - sum(v for _, v in lines) - net)
        k, v = lines[-1]
        lines[-1] = (k, _r2(v + diff))
        issuer = rng.choice(EMPLOYERS)
    elif kind == "pension":
        gross = net
        issuer = rng.choice(PENSION_FUNDS)
    else:
        rates = [("ahv", 0.053), ("alv", 0.0)]
        gross = _r2(net / (1 - 0.053))
        lines = [("ahv", _r2(gross - net))]
        issuer = "Caisse de chômage UNIA" if lang == "fr" else "Arbeitslosenkasse Kanton"
    deductions = _r2(sum(v for _, v in lines))
    truth = {
        "person_name": p.full_name,
        "period": "2024-12",
        "gross_monthly_income": gross,
        "net_monthly_income": net,
        "total_deductions": deductions,
        "issuer": issuer,
    }
    data = dict(kind=kind, issuer=issuer, period=(2024, 12), gross=gross, lines=lines,
                deductions=deductions, net=net, staff_no=f"{rng.randint(1000, 99999)}",
                ahv=f"756.{rng.randint(1000,9999)}.{rng.randint(1000,9999)}.{rng.randint(10,99)}",
                iban=fake_iban(rng))
    return DocContent("payslip", lang, p, data, truth,
                      {"monthly_net_income": net, "display_name": p.first_name})


def bank_statement(p: Person, rng: random.Random, lang: str | None = None) -> DocContent:
    lang = lang or p.lang
    closing = p.cash
    income = p.net_income
    rent = p.rent
    landlord = rng.choice(LANDLORDS)
    kind = {"retired": "tx_pension", "unemployed": "tx_benefit"}.get(p.employment_status, "tx_salary")
    # spending other than rent: 45-85% of what is left after rent, at least 250
    other = max(250.0, (income - rent) * rng.uniform(0.45, 0.85))
    txs = [(25, kind, income, "credit"), (1, "tx_rent", rent, "debit")]
    pieces = {
        "tx_insurance": rng.uniform(280, 520),
        "tx_phone": rng.choice([29.9, 39.0, 49.9, 65.0]),
        "tx_transport": rng.choice([49.0, 70.0, 85.0, 0.0]),
    }
    budget = other - sum(pieces.values())
    if budget < 60:
        pieces = {"tx_insurance": max(other - 60, 60)}
        budget = other - pieces["tx_insurance"]
    for k, v in pieces.items():
        if v > 0:
            txs.append((rng.randint(2, 12), k, _r2(v), "debit"))
    n_card = rng.randint(3, 6)
    cuts = sorted(rng.uniform(0, budget) for _ in range(n_card - 1))
    parts = [b - a for a, b in zip([0] + cuts, cuts + [budget])]
    for part in parts:
        k = rng.choice(["tx_card", "tx_card", "tx_atm", "tx_twint"])
        txs.append((rng.randint(2, 30), k, _r2(max(part, 5.0)), "debit"))
    txs.sort(key=lambda t: t[0])
    net_flow = _r2(sum(a if d == "credit" else -a for _, _, a, d in txs))
    opening = _r2(closing - net_flow)
    debits = _r2(sum(a for _, _, a, d in txs if d == "debit"))
    rows = []
    bal = opening
    for day, k, a, d in txs:
        bal = _r2(bal + (a if d == "credit" else -a))
        detail = rng.choice(SHOPS) if k == "tx_card" else ""
        rows.append(dict(day=day, key=k, amount=a, dir=d, balance=bal, detail=detail, landlord=landlord))
    truth = {
        "person_name": p.full_name,
        "period_end": "2024-12-31",
        "opening_balance": opening,
        "closing_balance": closing,
        "income_credit": income,
        "rent_debit": rent,
        "total_debits": debits,
    }
    data = dict(bank=rng.choice(BANKS), iban=fake_iban(rng), opening=opening, closing=closing, rows=rows)
    return DocContent("bank_statement", lang, p, data, truth, {
        "cash": closing, "monthly_net_income": income, "monthly_rent": rent,
        "monthly_other_expenses": _r2(debits - rent), "display_name": p.first_name})


def rental_contract(p: Person, rng: random.Random, lang: str | None = None) -> DocContent:
    lang = lang or p.lang
    total = p.rent
    parking = rng.choice([0, 0, 0, 120.0, 150.0]) if total > 1500 else 0
    charges = _r2(min(max(total * rng.uniform(0.08, 0.16), 80), 350))
    net_rent = _r2(total - charges - parking)
    deposit = _r2(3 * net_rent)
    start_year = rng.randint(2018, 2024)
    start = f"{start_year}-{rng.choice(['01','04','07','10'])}-01"
    landlord = rng.choice(LANDLORDS)
    truth = {
        "tenant_name": p.full_name,
        "landlord": landlord,
        "monthly_rent_net": net_rent,
        "monthly_charges": charges,
        "monthly_rent_total": total,
        "deposit": deposit,
        "lease_start": start,
        "city": p.city,
    }
    data = dict(landlord=landlord, net_rent=net_rent, charges=charges, parking=parking, total=total,
                deposit=deposit, start=start, rooms=rng.choice(["1.5", "2.5", "3", "3.5", "4.5"]),
                floor=rng.randint(1, 6))
    return DocContent("rental_contract", lang, p, data, truth,
                      {"monthly_rent": total, "city": p.city, "display_name": p.first_name})


def fake_iban(rng: random.Random) -> str:
    digits = "".join(str(rng.randint(0, 9)) for _ in range(17))
    raw = f"CH{rng.randint(10, 99)}{digits}"
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))


BUILDERS = {"payslip": payslip, "bank_statement": bank_statement, "rental_contract": rental_contract}
