# Multimodal roots

Turns documents (payslip, bank statement, rental contract), free text and voice notes into the
shared `Profile` (`docs/contracts.md`), with per-field provenance, and measures why this is
better than sending everything to a frontier model.

## The frugal chain

```
file ──► PDF text layer? ──yes──► text (free, ~0.1 s)
            │no
            └──► on-device OCR (RapidOCR / ONNX, CPU) ──► layout lines + OCR confidence
                        │
              OCR confidence < 0.85 or almost no text? ──yes──► image straight to the escalation VLM
                        │
              keyword doc-type classifier (free)
                        │
              small text LLM → JSON with a fixed schema   (mistral-small-24b, ~800 tokens, ~$0.00003)
                        │
              deterministic validation (free)
                ├ grounding: every number must literally appear in the document text
                ├ arithmetic: gross − deductions = net, net rent + charges ≤ total, ...
                └ per-field confidence = grounding × checks × OCR line confidence
                        │
              checks fail or a money field < 0.6 confidence?
                └──► escalate this document only: cheap VLM sees image + OCR text (gemini-3.1-flash-lite)
```

Derived values (e.g. `total_debits = opening + income − closing`) are computed in code, never asked to a model.
Free text and voice go through the same small model with a profile schema; every number is
checked against what the user actually said (`grounded`) and the source quote is kept.

## Use it (for the API thread)

```python
from multimodal import extract

out = extract(files=["payslip.jpg", ("statement.pdf", pdf_bytes)],
              text="I pay 900 rent", audio=None, audio_format="wav")
out["profile"]          # Profile per docs/contracts.md, with profile["provenance"][field]
out["documents"]        # per-document fields, confidence, checks, method, models, cost, latency
out["checks"]           # cross-source checks (e.g. payslip net == salary credit on the statement)
out["missing_fields"]   # core fields still unknown -> ask the user
out["cost_usd"], out["latency_ms"], out["extractor"]
```

`provenance[field] = {source, method, extractor, confidence, grounded, alternatives?, quote?}`.
Explicit user statements (text/voice) rank above documents; disagreements are kept as `alternatives`
and reported in `checks`.

Setup: `uv venv multimodal/.venv && uv pip install -p multimodal/.venv -r multimodal/requirements.txt`.
Needs `OPENROUTER_API_KEY` in `.env.local`. Every paid call is logged with its USD cost in
`multimodal/benchmark/results/spend_log.jsonl`.

## Synthetic documents

```
bash scripts/fetch_ubs_kit.sh                      # UBS synthetic profiles (not committed)
python -m multimodal.gen.generate --people 20      # -> data/synthetic/docs + manifest.jsonl
```

For each UBS profile we render a payslip (or pension / unemployment statement), a December bank
statement whose closing balance is the profile's opening cash, and a rental contract whose total
is the profile's rent. Language follows the canton (FR/DE/IT, ~15% EN). Names, employers,
addresses, IBANs and line items are invented. Each document is one of: clean PDF, scan (grey,
rotated, noisy), phone photo (perspective, shadow), low-res PNG, or *hard* (blurred, tiny, heavy
JPEG). `manifest.jsonl` holds the ground truth for every field.

## Benchmark

```
python -m multimodal.benchmark.run --strategies frugal ocr_llm vlm_small vlm_cheap vlm_large
```

Writes `multimodal/benchmark/results/<run_id>/{report.md, summary.json, per_doc.jsonl}`.
Headline results and interpretation: [`benchmark/RESULTS.md`](benchmark/RESULTS.md).
