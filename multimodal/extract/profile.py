"""Public entry point: documents / free text / voice -> Profile (docs/contracts.md) + provenance.

    from multimodal import extract
    out = extract(files=[("payslip.jpg", b"...")], text="I pay 900 rent", audio=None)
    out = {"profile": {...contract v1 Profile, unknown fields omitted..., "provenance": {...}},
           "extractor": "frugal: ...", "cost_usd": 0.00014, "latency_ms": 8200,
           "missing_fields": [...], "checks": [...], "documents": [...], "transcripts": [...]}

Every profile field carries provenance: where it came from (document + method, text,
voice), the model used, a confidence in [0, 1] and, for documents, whether the value
was literally found in the document (grounded).
"""
from __future__ import annotations

import base64
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import llm
from .documents import MODELS, extract_document
from .schema import PROFILE_MAP
from .validate import numbers_in, parse_number, strip_accents

# Contract v1 Profile keys. Unknown values are left out of the returned profile (the engine defaults
# missing optional fields to 0 / empty) and listed in `missing_fields` so the UI can ask for them.
PROFILE_DEFAULTS = {
    "profile_id": None, "display_name": None, "age": None, "city": None, "currency": "CHF",
    "as_of": None, "horizon_months": None, "employment_status": None, "cash": None, "monthly_net_income": None,
    "monthly_rent": None, "monthly_other_expenses": None, "monthly_investment_contribution": None,
    "assets": [], "liabilities": [], "goals": [],
}
CORE_FIELDS = ["monthly_net_income", "monthly_rent", "cash", "monthly_other_expenses", "employment_status",
               "age", "city"]
EMPLOYMENT = ["student", "employed", "part_time", "self_employed", "unemployed", "retired"]

FREE_TEXT_PROMPT = f"""You turn what a person says about their finances into JSON. The person may write or speak
in English, French, German, Italian or Spanish, informally ("I earn 1.2k a month", "je paie 900 de loyer").
Return one JSON object with these keys (null when not stated; never guess):
  "display_name": first name if given
  "age": integer
  "city": string
  "employment_status": one of {EMPLOYMENT}
  "monthly_net_income": number, CHF per month after tax (convert yearly to monthly by /12)
  "monthly_rent": number, CHF per month
  "monthly_other_expenses": number, CHF per month excluding rent
  "cash": number, current savings / cash in CHF
  "liabilities": list of {{"type": "student_loan|personal_loan|mortgage|other", "principal": number, "annual_rate": decimal|null (2% -> 0.02), "monthly_payment": number|null}}
  "goals": list of {{"name": string, "target": number|null, "target_date": "YYYY-MM-DD"|null}}
  "quotes": object mapping each non-null numeric key above to the exact words it came from
Money as plain numbers (1.200 or 1'200 means 1200; 1.2k means 1200)."""

AUDIO_PROMPT = ("Transcribe the audio verbatim in its original language, then extract fields. Return JSON "
                '{"transcript": "...", "fields": {...}} where fields follows these instructions:\n' + FREE_TEXT_PROMPT)

DOC_SOURCE = {"payslip": "payslip", "bank_statement": "bank_statement", "rental_contract": "rental_contract"}


def _income_kind(fields: dict) -> str | None:
    issuer = strip_accents(fields.get("issuer") or "")
    if any(k in issuer for k in ("compensation", "ausgleich", "assicurazioni", "pension", "rente", "avs", "ahv")):
        return "retired"
    if any(k in issuer for k in ("chomage", "arbeitslos", "disoccup", "unemploy", "unia")):
        return "unemployed"
    return None


def _free_text_fields(data: dict | None, source: str, said: str, model: str) -> tuple[dict, dict]:
    data = data or {}
    quotes = data.get("quotes") or {}
    nums = {x for x, _ in numbers_in(said)}
    said_l = strip_accents(said)
    fields, prov = {}, {}
    for k in ["display_name", "age", "city", "employment_status", "monthly_net_income", "monthly_rent",
              "monthly_other_expenses", "cash"]:
        v = data.get(k)
        if v in (None, "", []):
            continue
        if k in ("monthly_net_income", "monthly_rent", "monthly_other_expenses", "cash"):
            v = parse_number(v)
            if v is None:
                continue
            v = abs(v)
            # grounded if the number (or its thousands / yearly form) is in what the user said
            grounded = any(abs(n - v) < 0.01 or abs(n * 1000 - v) < 0.01 or abs(n / 12 - v) < 0.5 for n in nums)
        elif k == "age":
            try:
                v = int(v)
            except (TypeError, ValueError):
                continue
            grounded = str(v) in said
        elif k == "employment_status":
            if v not in EMPLOYMENT:
                continue
            grounded = True
        else:
            v = str(v)
            grounded = strip_accents(v) in said_l
        fields[k] = v
        prov[k] = {"source": source, "method": "llm", "extractor": model, "confidence": 0.85 if grounded else 0.5,
                   "grounded": grounded, "quote": quotes.get(k)}
    for k in ("liabilities", "goals"):
        if isinstance(data.get(k), list) and data[k]:
            fields[k] = data[k]
            prov[k] = {"source": source, "extractor": model, "confidence": 0.6, "grounded": None}
    return fields, prov


def from_text(text: str, source: str = "text", tag: str = "") -> dict:
    r = llm.chat(MODELS["text_small"], [{"role": "system", "content": FREE_TEXT_PROMPT},
                                        {"role": "user", "content": text}], tag=f"{tag}:free_text")
    fields, prov = _free_text_fields(r.data, source, text, r.model)
    return {"fields": fields, "provenance": prov, "cost_usd": r.cost_usd, "seconds": r.seconds, "transcript": text}


def from_audio(audio: bytes, fmt: str = "wav", tag: str = "") -> dict:
    b64 = base64.b64encode(audio).decode()
    r = llm.chat(MODELS["audio"], [{"role": "system", "content": AUDIO_PROMPT}, {"role": "user", "content": [
        {"type": "input_audio", "input_audio": {"data": b64, "format": fmt}}]}], tag=f"{tag}:audio", max_tokens=900)
    d = r.data or {}
    transcript = d.get("transcript") or ""
    fields, prov = _free_text_fields(d.get("fields"), "voice", transcript, r.model)
    return {"fields": fields, "provenance": prov, "cost_usd": r.cost_usd, "seconds": r.seconds, "transcript": transcript}


def _source(doc_type: str, method: str) -> str:
    """Contract-style source label: payslip_ocr, bank_statement_pdf_text, rental_contract_vlm, ..."""
    kind = "vlm" if "vlm" in method else ("pdf_text" if method.startswith("pdf_text") else "ocr")
    return f"{doc_type}_{kind}"


def extractor_label(strategy: str = "frugal") -> str:
    if strategy in ("frugal", "ocr_llm"):
        esc = f" (+{MODELS['escalation_vlm']} on failed checks / unreadable captures)" if strategy == "frugal" else ""
        return f"{strategy}: pdf text / rapidocr (local) + {MODELS['text_small']}{esc}"
    return f"{strategy}: {MODELS[strategy]}"


def _clean_liability(l: dict) -> dict:
    out = {"type": l.get("type") or "other", "label": l.get("label") or (l.get("type") or "loan").replace("_", " ").capitalize()}
    for k in ("principal", "annual_rate", "monthly_payment"):
        v = parse_number(l.get(k)) if l.get(k) is not None else None
        out[k] = abs(v) if v is not None else 0.0
    if out["annual_rate"] > 1:  # "2%" said as 2
        out["annual_rate"] = round(out["annual_rate"] / 100, 4)
    return out


def _read(f) -> tuple[str, bytes]:
    if isinstance(f, tuple):
        return f[0], f[1]
    p = Path(f)
    return p.name, p.read_bytes()


def extract(files=None, text: str | None = None, audio: bytes | None = None, audio_format: str = "wav",
            strategy: str = "frugal", base_profile: dict | None = None) -> dict:
    """files: list of paths or (filename, bytes). Later inputs override earlier ones only when more confident."""
    t0 = time.perf_counter()
    profile = {**PROFILE_DEFAULTS, **(base_profile or {})}
    provenance: dict = dict((base_profile or {}).get("provenance") or {})
    candidates: dict[str, list] = {}
    docs_out, cost = [], 0.0

    named = [_read(f) for f in files or []]
    with ThreadPoolExecutor(max_workers=6) as ex:
        doc_futs = [ex.submit(extract_document, data, strategy, "api") for _, data in named]
        text_fut = ex.submit(from_text, text, "text", "api") if text else None
        audio_fut = ex.submit(from_audio, audio, audio_format, "api") if audio else None
        doc_results = [fu.result() for fu in doc_futs]
        free_parts = [fu.result() for fu in (text_fut, audio_fut) if fu is not None]

    for (name, _), res in zip(named, doc_results):
        cost += res.cost_usd
        docs_out.append({"filename": name, **res.to_dict()})
        for pf, sources in PROFILE_MAP.items():
            for rank, (dt, df) in enumerate(sources):
                if res.doc_type == dt and res.fields.get(df) is not None:
                    c = res.confidence.get(df, {})
                    candidates.setdefault(pf, []).append((rank, res.fields[df], {
                        "source": _source(dt, res.method), "file": name, "field": df, "method": res.method,
                        "extractor": "+".join(res.models),
                        "confidence": c.get("confidence"), "grounded": c.get("grounded")}))
        if res.doc_type == "bank_statement" and res.fields.get("total_debits") is not None \
                and res.fields.get("rent_debit") is not None:
            candidates.setdefault("monthly_other_expenses", []).append((0, round(
                res.fields["total_debits"] - res.fields["rent_debit"], 2), {
                "source": _source("bank_statement", res.method), "file": name,
                "method": "derived: opening + income - closing - rent",
                "extractor": "+".join(res.models), "confidence": res.confidence["total_debits"]["confidence"],
                "grounded": False}))
        if res.doc_type == "payslip":
            kind = _income_kind(res.fields) or "employed"
            candidates.setdefault("employment_status", []).append((1, kind, {
                "source": _source("payslip", res.method), "file": name, "method": "issuer keywords",
                "extractor": "rules",
                "confidence": 0.6, "grounded": None}))

    transcripts = []
    for part in free_parts:
        cost += part["cost_usd"]
        transcripts.append(part["transcript"])
        for k, v in part["fields"].items():
            if k in ("liabilities", "goals"):
                profile[k] = [_clean_liability(x) for x in v if isinstance(x, dict)] if k == "liabilities" else v
                provenance[k] = part["provenance"][k]
            else:
                # what the user states explicitly is ranked first; documents back it up
                candidates.setdefault(k, []).append((-1, v, part["provenance"][k]))

    checks = []
    for pf, cands in candidates.items():
        cands.sort(key=lambda c: (c[0], -(c[2].get("confidence") or 0)))
        best = cands[0]
        profile[pf] = best[1]
        prov = dict(best[2])
        nums = [c for c in cands if isinstance(c[1], (int, float))]
        if len(nums) > 1:
            agree = all(abs(c[1] - best[1]) <= max(1.0, 0.01 * abs(best[1])) for c in nums)
            checks.append({"name": f"cross_source_{pf}", "passed": agree,
                           "values": [{"value": c[1], "source": c[2]["source"], "file": c[2].get("file")} for c in nums]})
            if agree and prov.get("confidence") is not None:
                prov["confidence"] = round(min(1.0, prov["confidence"] + 0.1), 3)
            prov["alternatives"] = [{"value": c[1], "source": c[2]["source"], "file": c[2].get("file")}
                                    for c in cands[1:]]
        provenance[pf] = prov

    if profile.get("display_name"):
        profile["display_name"] = str(profile["display_name"]).split()[0]  # first name, as in the contract
    for g in profile.get("goals") or []:
        if isinstance(g, dict):
            g.setdefault("priority", "medium")
            g.setdefault("metric", "liquid")
    missing = [k for k in CORE_FIELDS if profile.get(k) in (None, "")]
    profile = {k: v for k, v in profile.items() if v is not None}
    profile["provenance"] = provenance
    return {"profile": profile, "extractor": extractor_label(strategy), "cost_usd": round(cost, 6),
            "latency_ms": int((time.perf_counter() - t0) * 1000), "missing_fields": missing, "checks": checks,
            "documents": docs_out, "transcripts": transcripts}
