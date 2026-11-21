# Extraction benchmark (20261121-144926)

12 synthetic Swiss documents (payslips, bank statements, rental contracts; FR/DE/IT/EN; clean PDF, scanned, phone photo, low-res) with known ground truth.

| Strategy | Models | Field accuracy | Key-field accuracy | USD / doc | USD per 1,000 docs | Latency p50 (s) | Escalated |
|---|---|---|---|---|---|---|---|
| frugal | local OCR + mistralai/mistral-small-24b-instruct-2501 (+google/gemini-2.5-flash-lite on failed checks) | 100.0% | 100.0% | 0.000057 | 0.06 | 5.71 | 17% |
| vlm_small | google/gemma-3-12b-it | 76.6% | 72.2% | 0.000131 | 0.13 | 4.52 | 0% |
| vlm_large | anthropic/claude-fable-5.2 | 99.0% | 100.0% | 0.029033 | 29.03 | 5.83 | 0% |

## Field accuracy by variant

| Strategy | lowres | pdf | photo | scan |
|---|---|---|---|---|
| frugal | 100.0% | 100.0% | 100.0% | 100.0% |
| vlm_small | 67.5% | 67.3% | 80.2% | 91.7% |
| vlm_large | 100.0% | 95.8% | 100.0% | 100.0% |

## Field accuracy by doc_type

| Strategy | bank_statement | payslip | rental_contract |
|---|---|---|---|
| frugal | 100.0% | 100.0% | 100.0% |
| vlm_small | 64.3% | 87.5% | 78.1% |
| vlm_large | 100.0% | 100.0% | 96.9% |

## Field accuracy by lang

| Strategy | de | en | fr | it |
|---|---|---|---|---|
| frugal | 100.0% | 100.0% | 100.0% | 100.0% |
| vlm_small | 74.6% | 86.6% | 78.9% | 69.0% |
| vlm_large | 100.0% | 93.8% | 100.0% | 100.0% |

Key fields = the ones that feed the Profile (net income, rent, cash). Costs as reported by OpenRouter.
Latency includes local OCR on a laptop CPU for the frugal strategies.
