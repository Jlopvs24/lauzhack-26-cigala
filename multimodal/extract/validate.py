"""Deterministic checks on extracted fields: normalisation, grounding, arithmetic, confidence.

The model proposes values; this module decides how much to trust them:
- grounding: does the value literally appear in the document text? (anti-hallucination)
- arithmetic: do the numbers add up (gross - deductions = net, net + charges = total, ...)?
- confidence: combines both with OCR confidence of the line the value came from.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from .schema import DERIVED, FIELDS

NUM_RE = re.compile(r"-?\d{1,3}(?:[’'` ,.]\d{3})+(?:[.,]\d{1,2})?|-?\d+[.,]\d{2}|-?\d+")
TOL = 0.051


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def parse_number(tok) -> float | None:
    if tok is None:
        return None
    if isinstance(tok, (int, float)):
        return round(float(tok), 2)
    s = str(tok).strip().replace("CHF", "").replace("Fr.", "").replace("−", "-").strip()
    s = re.sub(r"\s", " ", s)
    m = re.search(r"-?\d[\d’'` ,.]*", s)
    if not m:
        return None
    s = m.group(0).rstrip(".,' ")
    neg = s.startswith("-")
    s = s.lstrip("-")
    dec = re.search(r"[.,](\d{1,2})$", s)
    if dec:
        intpart, frac = s[:dec.start()], dec.group(1)
    else:
        intpart, frac = s, "0"
    intpart = re.sub(r"[^\d]", "", intpart)
    if not intpart:
        return None
    v = float(f"{intpart}.{frac}")
    return round(-v if neg else v, 2)


def numbers_in(text: str) -> list[tuple[float, int]]:
    """All money-like numbers in text with the line index they occur on."""
    out = []
    for i, line in enumerate(text.splitlines()):
        for m in NUM_RE.finditer(line):
            v = parse_number(m.group(0))
            if v is not None:
                out.append((abs(v), i))
    return out


def norm_date(v) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", s):
        return s
    m = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return s


def normalise(doc_type: str, raw: dict) -> dict:
    out = {}
    for k, (t, _) in FIELDS[doc_type].items():
        v = raw.get(k) if raw else None
        if t == "money":
            v = parse_number(v)
            if v is not None and k != "opening_balance" and k != "closing_balance":
                v = abs(v)
        elif t in ("date", "month"):
            v = norm_date(v)
            if t == "month" and v and len(v) >= 7:
                v = v[:7]
        else:
            v = str(v).strip() if v not in (None, "") else None
        out[k] = v
    for k, expr in DERIVED.get(doc_type, {}).items():
        try:
            out[k] = round(eval(expr, {}, {f: out[f] for f in FIELDS[doc_type]}), 2)
        except TypeError:
            out[k] = None
    return out


def _close(a, b) -> bool:
    return a is not None and b is not None and abs(a - b) <= TOL


def arithmetic_checks(doc_type: str, f: dict) -> list[dict]:
    checks = []
    if doc_type == "payslip":
        g, d, n = f["gross_monthly_income"], f["total_deductions"], f["net_monthly_income"]
        if None not in (g, d, n):
            checks.append({"name": "gross_minus_deductions_equals_net", "passed": _close(g - d, n),
                           "fields": ["gross_monthly_income", "total_deductions", "net_monthly_income"]})
        if g is not None and n is not None:
            checks.append({"name": "net_not_above_gross", "passed": n <= g + TOL,
                           "fields": ["gross_monthly_income", "net_monthly_income"]})
    elif doc_type == "bank_statement":
        td = f.get("total_debits")
        if td is not None:
            checks.append({"name": "debits_cover_rent", "passed": td + TOL >= (f["rent_debit"] or 0),
                           "fields": ["opening_balance", "closing_balance", "income_credit", "rent_debit"]})
    elif doc_type == "rental_contract":
        nr, ch, tot = f["monthly_rent_net"], f["monthly_charges"], f["monthly_rent_total"]
        if None not in (nr, ch, tot):
            # parking may sit between net+charges and total, so allow total >= net + charges
            checks.append({"name": "net_plus_charges_le_total", "passed": nr + ch <= tot + TOL,
                           "fields": ["monthly_rent_net", "monthly_charges", "monthly_rent_total"]})
    return checks


def confidence(doc_type: str, f: dict, text: str, line_conf: list[float] | None = None,
               grounding: bool = True) -> tuple[dict, list[dict]]:
    """grounding=False when no trustworthy local text exists (image read by a VLM only)."""
    nums = numbers_in(text)
    ntext = strip_accents(text)
    checks = arithmetic_checks(doc_type, f)
    conf = {}
    for k, (t, _) in FIELDS[doc_type].items():
        v = f.get(k)
        if v is None:
            conf[k] = {"confidence": 0.0, "grounded": False}
            continue
        grounded, oc = False, 1.0
        if t == "money":
            hits = [i for x, i in nums if abs(x - abs(v)) <= 0.005]
            grounded = bool(hits) or v == 0
            if hits and line_conf:
                oc = max(line_conf[i] for i in hits if i < len(line_conf)) if any(i < len(line_conf) for i in hits) else 1.0
        elif t == "text":
            toks = [w for w in re.findall(r"\w+", strip_accents(v)) if len(w) > 1]
            grounded = bool(toks) and sum(w in ntext for w in toks) / len(toks) >= 0.75
        else:
            grounded = bool(re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", v))
        if not grounding:
            grounded = None
        c = 0.6 if grounded is None else (0.85 if grounded else 0.35)
        for ch in checks:
            if k in ch["fields"]:
                c += 0.1 if ch["passed"] else -0.3
        c = max(0.0, min(1.0, c)) * (0.5 + 0.5 * oc)
        conf[k] = {"confidence": round(c, 3), "grounded": grounded}
    for k in DERIVED.get(doc_type, {}):
        src = [conf[x]["confidence"] for x in ("opening_balance", "income_credit", "closing_balance")]
        conf[k] = {"confidence": round(min(src), 3) if f.get(k) is not None else 0.0, "grounded": False, "derived": True}
    return conf, checks


def needs_escalation(doc_type: str, f: dict, conf: dict, checks: list[dict], min_conf: float = 0.6) -> list[str]:
    reasons = [c["name"] for c in checks if not c["passed"]]
    for k, (t, _) in FIELDS[doc_type].items():
        if t == "money" and conf[k]["confidence"] < min_conf:
            reasons.append(f"low_confidence:{k}")
    return reasons
