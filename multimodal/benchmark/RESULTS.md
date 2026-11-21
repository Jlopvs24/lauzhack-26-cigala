# Why we don't send everything to the big model

Run `20261121-151135` (vlm_small / vlm_large rows reused from `20261121-145235`, same 60 documents).
60 synthetic Swiss documents with known ground truth: 20 UBS profiles × payslip, bank statement and
rental contract, in FR / DE / IT / EN, as clean PDF, scan, phone photo, low-res image or a
deliberately *hard* capture (blurred, tiny, heavy JPEG). Cost is what OpenRouter billed per call.

| Strategy | Field accuracy | Key fields* | USD / doc | USD / 1,000 docs | Images sent to a cloud model |
|---|---|---|---|---|---|
| **Frugal chain (ours)**: PDF text or local OCR → mistral-small-24b → checks → gemini-3.1-flash-lite only if needed | **97.7%** | **97.8%** | **0.00019** | **0.19** | **27%** |
| Same chain without escalation | 83.3% | 82.8% | 0.00003 | 0.03 | 0% |
| Cheap VLM on every image (gemini-3.1-flash-lite) | 97.9% | 97.8% | 0.00060 | 0.60 | 100% |
| Small open VLM on every image (gemma-3-12b) | 77.7% | 76.7% | 0.00016 | 0.16 | 100% |
| Frontier VLM on every image (claude-fable-5.2) | 99.4% | 100.0% | 0.02876 | 28.76 | 100% |

\* Key fields feed the Profile: net income, rent, cash (closing balance), salary credit, rent debit.

What we take from it:

- **154× cheaper than the frontier model for 1.7 points of accuracy.** The frugal chain matches the cheap
  VLM's accuracy at a third of its cost, because 73% of documents never need a vision model: a PDF's
  own text layer or on-device OCR plus an 800-token call to a small model is enough.
- **Escalation is earned, not default.** Every number the small model returns must literally appear in
  the document text and must add up (gross − deductions = net, net rent + charges ≤ total). Only when a
  check fails, or OCR confidence says the photo is unreadable, does that one document go to a VLM.
  Without this step accuracy drops to 83% (the *hard* captures fall to 26%).
- **Privacy follows from frugality.** Clean PDFs and decent photos are read on the laptop; only text
  snippets reach the small model, and only 27% of images ever leave the device.
- **Small VLMs are not the frugal answer.** gemma-3-12b costs about what our chain costs and is 20 points
  worse: it misreads Swiss number formats (1'234.50, 1 234,50) and confuses opening/closing balances.
- **Where we still lose:** bank statements in the *hard* set (tiny, blurred tables). The frontier model
  reads them; we would rather ask the user for a better photo than pay 150× on every document.

By variant (field accuracy):

| Strategy | pdf | scan | photo | lowres | hard |
|---|---|---|---|---|---|
| Frugal chain | 100.0% | 100.0% | 99.0% | 99.0% | 90.6% |
| No escalation | 100.0% | 98.8% | 95.4% | 96.6% | 25.8% |
| gemini-3.1-flash-lite | 100.0% | 100.0% | 100.0% | 99.0% | 90.6% |
| gemma-3-12b | 86.3% | 84.4% | 86.3% | 87.0% | 44.8% |
| claude-fable-5.2 | 100.0% | 100.0% | 100.0% | 99.0% | 97.9% |

How we chose the escalation model: on the 12 *hard* documents, image only — gemini-3.1-flash-lite 90.6%
($0.0006/doc), gemini-2.5-flash 78.7%, qwen3-vl-30b 66.9%, claude-haiku-5.5 65.2%.

Latency (p50, laptop CPU): frugal 5.1 s/doc (OCR ~2–4 s), flash-lite 2.4 s, Fable 4.8 s. Documents of
one upload are processed in parallel.

Caveats: documents are synthetic and rendered by our own generator; the extraction prompts and code never
see the generator's templates, but real documents are messier. Full per-document results:
`results/20261121-151135/per_doc.jsonl`; reproduce with
`python -m multimodal.benchmark.run --strategies frugal ocr_llm vlm_cheap vlm_small vlm_large`.
Total API spend for all experiments so far: USD 2.14 (see `results/spend_log.jsonl`).
