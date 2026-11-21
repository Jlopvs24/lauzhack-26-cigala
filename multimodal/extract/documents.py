"""Per-document extraction strategies.

frugal     : local text (PDF layer / on-device OCR) -> keyword doc-type -> small text LLM (JSON)
             -> deterministic validation -> escalate to a cheap VLM only if checks fail.
ocr_llm    : same without escalation (ablation).
vlm_small  : image straight into a small open vision model.
vlm_cheap  : image straight into a cheap proprietary vision model.
vlm_large  : image straight into a frontier vision model ("send everything to the big model").
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import llm
from .schema import DOC_TYPES, FIELDS, TYPE_KEYWORDS
from .text import get_text, is_pdf, load_image, pdf_to_image
from .validate import confidence, needs_escalation, normalise, strip_accents

MODELS = {
    "text_small": "mistralai/mistral-small-24b-instruct-2501",
    "escalation_vlm": "google/gemini-3.1-flash-lite",
    "vlm_small": "google/gemma-3-12b-it",
    "vlm_cheap": "google/gemini-3.1-flash-lite",
    "vlm_large": "anthropic/claude-fable-5.2",
    "audio": "google/gemini-2.5-flash-lite",
}

RULES = """Rules:
- Copy values exactly as printed; do not guess. Use null if a field is not on the document.
- Money: plain JSON numbers in CHF with a dot as decimal separator, no thousands separators, no currency
  (e.g. "Fr. 1'234.50" or "1 234,50" -> 1234.5). Deductions and debits as positive numbers.
- Dates as YYYY-MM-DD, months as YYYY-MM.
- The document may be in French, German, Italian or English. Output keys stay in English."""


def _fields_block(doc_type: str) -> str:
    return "\n".join(f'  "{k}": {t} - {d}' for k, (t, d) in FIELDS[doc_type].items())


def prompt_single(doc_type: str) -> str:
    return (f"You extract fields from a Swiss {doc_type.replace('_', ' ')}. Return one JSON object with exactly "
            f"these keys:\n{_fields_block(doc_type)}\n{RULES}")


def prompt_any() -> str:
    blocks = "\n".join(f'doc_type "{dt}":\n{_fields_block(dt)}' for dt in DOC_TYPES)
    return ("You read one Swiss financial document. First decide its doc_type, then extract its fields. "
            'Return JSON: {"doc_type": "...", "fields": {...}} where fields has exactly the keys of that doc_type:\n'
            f"{blocks}\n{RULES}")


def classify(text: str) -> tuple[str, float]:
    t = strip_accents(text)
    scores = {dt: sum(t.count(k) for k in kws) for dt, kws in TYPE_KEYWORDS.items()}
    # titles near the top weigh more
    head = strip_accents("\n".join(text.splitlines()[:8]))
    for dt, kws in TYPE_KEYWORDS.items():
        scores[dt] += 2 * sum(k in head for k in kws)
    best = max(scores, key=scores.get)
    tot = sum(scores.values()) or 1
    return best, round(scores[best] / tot, 3)


@dataclass
class DocResult:
    doc_type: str
    fields: dict
    confidence: dict
    checks: list
    method: str
    models: list = field(default_factory=list)
    cost_usd: float = 0.0
    seconds: float = 0.0
    escalated: bool = False
    escalation_reasons: list = field(default_factory=list)
    text_chars: int = 0

    def to_dict(self):
        return self.__dict__.copy()


def _image(data: bytes):
    return pdf_to_image(data, dpi=150) if is_pdf(data) else load_image(data)


UNREADABLE_CONF = 0.85   # mean OCR confidence below this = capture too poor for OCR
UNREADABLE_CHARS = 150


def extract_frugal(data: bytes, *, escalate: bool = True, tag: str = "") -> DocResult:
    t0 = time.perf_counter()
    tr = get_text(data)
    if escalate and tr.method == "ocr" and (tr.mean_conf < UNREADABLE_CONF or len(tr.text) < UNREADABLE_CHARS):
        # OCR output is noise: do not pay a text model to read it, send the image to the escalation VLM
        res = extract_vlm(data, "escalation_vlm", tag=f"{tag}:unreadable")
        f = res.fields
        conf, checks = confidence(res.doc_type, f, "", None, grounding=False)
        res = DocResult(res.doc_type, f, conf, checks, "ocr_unreadable->vlm", res.models, res.cost_usd, 0, True,
                        [f"unreadable_capture(ocr_conf={tr.mean_conf:.2f}, chars={len(tr.text)})"], len(tr.text))
        res.seconds = time.perf_counter() - t0
        return res
    doc_type, _ = classify(tr.text)
    line_conf = [c for _, c in tr.lines]
    r = llm.chat(MODELS["text_small"], [
        {"role": "system", "content": prompt_single(doc_type)},
        {"role": "user", "content": f"Document text ({tr.method}):\n{tr.text}"}], tag=f"{tag}:text_small")
    f = normalise(doc_type, r.data or {})
    conf, checks = confidence(doc_type, f, tr.text, line_conf)
    res = DocResult(doc_type, f, conf, checks, f"{tr.method}+llm", [r.model], r.cost_usd, 0, text_chars=len(tr.text))
    reasons = needs_escalation(doc_type, f, conf, checks)
    if escalate and reasons:
        img = _image(data)
        r2 = llm.chat(MODELS["escalation_vlm"], [
            {"role": "system", "content": prompt_single(doc_type)},
            {"role": "user", "content": [
                {"type": "text", "text": f"OCR text (may contain errors):\n{tr.text}\n\nThe image is authoritative."},
                llm.image_part(img)]}], tag=f"{tag}:escalation")
        f2 = normalise(doc_type, r2.data or {})
        conf2, checks2 = confidence(doc_type, f2, tr.text, line_conf)
        # fields in a failed arithmetic check come from the VLM if its values add up
        failed = {k for c in checks if not c["passed"] for k in c["fields"]}
        vlm_consistent = all(c["passed"] for c in checks2)
        for k in f:
            if (k in failed and vlm_consistent and f2.get(k) is not None) or                     conf2.get(k, {}).get("confidence", 0) > conf[k]["confidence"]:
                f[k], conf[k] = f2[k], conf2[k]
        f = normalise(doc_type, f)
        conf, checks = confidence(doc_type, f, tr.text, line_conf)
        res = DocResult(doc_type, f, conf, checks, f"{tr.method}+llm+vlm_escalation", [r.model, r2.model],
                        r.cost_usd + r2.cost_usd, 0, True, reasons, len(tr.text))
    res.seconds = time.perf_counter() - t0
    return res


def extract_vlm(data: bytes, which: str, tag: str = "") -> DocResult:
    t0 = time.perf_counter()
    img = _image(data)
    r = llm.chat(MODELS[which], [
        {"role": "system", "content": prompt_any()},
        {"role": "user", "content": [{"type": "text", "text": "Extract the document."}, llm.image_part(img)]}],
        tag=f"{tag}:{which}", max_tokens=700)
    d = r.data or {}
    doc_type = d.get("doc_type") if d.get("doc_type") in DOC_TYPES else "payslip"
    f = normalise(doc_type, d.get("fields") or {})
    # no local text for VLM-only strategies: grounding is unavailable, confidence is not computed
    conf = {k: {"confidence": None, "grounded": None} for k in f}
    return DocResult(doc_type, f, conf, [], which, [r.model], r.cost_usd, time.perf_counter() - t0)


def extract_document(src: bytes | str | Path, strategy: str = "frugal", tag: str = "") -> DocResult:
    data = src if isinstance(src, bytes) else Path(src).read_bytes()
    if strategy == "frugal":
        return extract_frugal(data, tag=tag)
    if strategy == "ocr_llm":
        return extract_frugal(data, escalate=False, tag=tag)
    if strategy in ("vlm_small", "vlm_cheap", "vlm_large"):
        return extract_vlm(data, strategy, tag=tag)
    raise ValueError(strategy)


if __name__ == "__main__":
    import sys
    res = extract_document(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "frugal", tag="cli")
    print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
