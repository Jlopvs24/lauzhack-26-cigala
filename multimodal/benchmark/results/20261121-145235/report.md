# Extraction benchmark (20261121-145235)

60 synthetic Swiss documents (payslips, bank statements, rental contracts; FR/DE/IT/EN; clean PDF, scanned, phone photo, low-res) with known ground truth.

| Strategy | Models | Field accuracy | Key-field accuracy | USD / doc | USD per 1,000 docs | Latency p50 (s) | Escalated |
|---|---|---|---|---|---|---|---|
| frugal | local OCR + mistralai/mistral-small-24b-instruct-2501 (+google/gemini-2.5-flash-lite on failed checks) | 79.2% | 80.0% | 0.000061 | 0.06 | 5.62 | 25% |
| ocr_llm | local OCR + mistralai/mistral-small-24b-instruct-2501 | 84.7% | 84.4% | 0.000035 | 0.03 | 3.61 | 0% |
| vlm_small | google/gemma-3-12b-it | 77.7% | 76.7% | 0.000164 | 0.16 | 2.99 | 0% |
| vlm_cheap | google/gemini-2.5-flash-lite | 71.9% | 69.4% | 0.000131 | 0.13 | 1.76 | 0% |
| vlm_large | anthropic/claude-fable-5.2 | 99.4% | 100.0% | 0.028762 | 28.76 | 4.8 | 0% |

## Field accuracy by variant

| Strategy | hard | lowres | pdf | photo | scan |
|---|---|---|---|---|---|
| frugal | 45.7% | 96.6% | 83.3% | 95.4% | 75.0% |
| ocr_llm | 32.5% | 96.6% | 100.0% | 95.4% | 98.8% |
| vlm_small | 44.8% | 87.0% | 86.3% | 86.3% | 84.4% |
| vlm_cheap | 58.0% | 65.6% | 76.0% | 77.4% | 82.4% |
| vlm_large | 97.9% | 99.0% | 100.0% | 100.0% | 100.0% |

## Field accuracy by doc_type

| Strategy | bank_statement | payslip | rental_contract |
|---|---|---|---|
| frugal | 64.3% | 90.8% | 82.5% |
| ocr_llm | 78.6% | 94.2% | 81.2% |
| vlm_small | 70.7% | 90.0% | 72.5% |
| vlm_cheap | 77.1% | 44.2% | 94.4% |
| vlm_large | 100.0% | 100.0% | 98.1% |

## Field accuracy by lang

| Strategy | de | en | fr | it |
|---|---|---|---|---|
| frugal | 75.2% | 70.9% | 91.5% | 73.8% |
| ocr_llm | 79.7% | 67.3% | 91.5% | 90.5% |
| vlm_small | 70.0% | 60.2% | 87.3% | 83.9% |
| vlm_cheap | 72.7% | 69.4% | 75.7% | 67.7% |
| vlm_large | 98.7% | 100.0% | 99.3% | 100.0% |

Key fields = the ones that feed the Profile (net income, rent, cash). Costs as reported by OpenRouter.
Latency includes local OCR on a laptop CPU for the frugal strategies.
