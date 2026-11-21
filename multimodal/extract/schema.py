"""Field definitions per document type and how they map onto the shared Profile."""
from __future__ import annotations

# field -> (type, description). Types: money | text | date | month
FIELDS: dict[str, dict[str, tuple[str, str]]] = {
    "payslip": {
        "person_name": ("text", "full name of the employee / beneficiary"),
        "period": ("month", "pay period as YYYY-MM"),
        "gross_monthly_income": ("money", "gross salary / gross pension / gross benefit for the month"),
        "total_deductions": ("money", "sum of all deductions (positive number), 0 if none"),
        "net_monthly_income": ("money", "net amount actually paid out for the month"),
        "issuer": ("text", "employer, pension fund or benefit office"),
    },
    "bank_statement": {
        "person_name": ("text", "account holder full name"),
        "period_end": ("date", "last day covered, YYYY-MM-DD"),
        "opening_balance": ("money", "balance at the start of the period"),
        "closing_balance": ("money", "balance at the end of the period"),
        "income_credit": ("money", "the salary / pension / benefit credit of the month"),
        "rent_debit": ("money", "the rent payment of the month"),
    },
    "rental_contract": {
        "tenant_name": ("text", "tenant full name"),
        "landlord": ("text", "landlord or property manager"),
        "monthly_rent_net": ("money", "net monthly rent without charges"),
        "monthly_charges": ("money", "monthly service charges (advance)"),
        "monthly_rent_total": ("money", "total monthly amount the tenant pays (rent + charges + parking)"),
        "deposit": ("money", "security deposit"),
        "lease_start": ("date", "lease start, YYYY-MM-DD"),
        "city": ("text", "city of the rented property"),
    },
}

DOC_TYPES = list(FIELDS)

# fields computed deterministically from extracted ones (never asked to a model)
DERIVED = {
    "bank_statement": {"total_debits": "opening_balance + income_credit - closing_balance"},
}

# Profile field <- [(doc_type, doc_field)] in order of preference
PROFILE_MAP = {
    "monthly_net_income": [("payslip", "net_monthly_income"), ("bank_statement", "income_credit")],
    "monthly_rent": [("rental_contract", "monthly_rent_total"), ("bank_statement", "rent_debit")],
    "cash": [("bank_statement", "closing_balance")],
    "city": [("rental_contract", "city")],
    "display_name": [("payslip", "person_name"), ("bank_statement", "person_name"), ("rental_contract", "tenant_name")],
}

# keywords used for free, local document-type classification (lowercase, accents stripped)
TYPE_KEYWORDS = {
    "payslip": ["salaire", "lohn", "gehalt", "salario", "payslip", "salary", "pay statement", "rente", "rendita",
                "pension", "chomage", "arbeitslosen", "disoccupazione", "unemployment", "ahv", "avs", "busta paga"],
    "bank_statement": ["releve de compte", "extrait de compte", "kontoauszug", "auszug privatkonto", "estratto conto",
                       "account statement", "bank statement", "solde", "saldo", "balance", "iban"],
    "rental_contract": ["bail", "mietvertrag", "locazione", "tenancy", "lease", "locataire", "mieter", "conduttore",
                        "tenant", "garantie", "kaution", "deposit", "pigione", "loyer"],
}


def json_schema(doc_type: str) -> dict:
    props = {}
    for k, (t, desc) in FIELDS[doc_type].items():
        props[k] = {"type": ["number", "null"] if t == "money" else ["string", "null"], "description": desc}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
