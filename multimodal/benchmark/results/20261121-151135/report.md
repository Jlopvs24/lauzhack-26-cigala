# Extraction benchmark (20261121-151135)

60 synthetic Swiss documents (payslips, bank statements, rental contracts; FR/DE/IT/EN; clean PDF, scanned, phone photo, low-res) with known ground truth.

| Strategy | Models | Field accuracy | Key-field accuracy | USD / doc | USD per 1,000 docs | Latency p50 (s) | Escalated |
|---|---|---|---|---|---|---|---|
| frugal | local OCR + mistralai/mistral-small-24b-instruct-2501 (+google/gemini-3.1-flash-lite on failed checks / unreadable captures) | 97.7% | 97.8% | 0.000187 | 0.19 | 5.11 | 27% |
| ocr_llm | local OCR + mistralai/mistral-small-24b-instruct-2501 | 83.3% | 82.8% | 0.000034 | 0.03 | 4.2 | 0% |
| vlm_cheap | google/gemini-3.1-flash-lite | 97.9% | 97.8% | 0.000596 | 0.60 | 2.36 | 0% |
| vlm_small | google/gemma-3-12b-it | 77.7% | 76.7% | 0.000164 | 0.16 | 2.99 | 0% |
| vlm_large | anthropic/claude-fable-5.2 | 99.4% | 100.0% | 0.028762 | 28.76 | 4.8 | 0% |

## Field accuracy by variant

| Strategy | hard | lowres | pdf | photo | scan |
|---|---|---|---|---|---|
| frugal | 90.6% | 99.0% | 100.0% | 99.0% | 100.0% |
| ocr_llm | 25.8% | 96.6% | 100.0% | 95.4% | 98.8% |
| vlm_cheap | 90.6% | 99.0% | 100.0% | 100.0% | 100.0% |
| vlm_small | 44.8% | 87.0% | 86.3% | 86.3% | 84.4% |
| vlm_large | 97.9% | 99.0% | 100.0% | 100.0% | 100.0% |

## Field accuracy by doc_type

| Strategy | bank_statement | payslip | rental_contract |
|---|---|---|---|
| frugal | 95.0% | 100.0% | 98.1% |
| ocr_llm | 77.9% | 90.8% | 81.2% |
| vlm_cheap | 95.0% | 100.0% | 98.8% |
| vlm_small | 70.7% | 90.0% | 72.5% |
| vlm_large | 100.0% | 100.0% | 98.1% |

## Field accuracy by lang

| Strategy | de | en | fr | it |
|---|---|---|---|---|
| frugal | 97.1% | 100.0% | 96.2% | 99.1% |
| ocr_llm | 79.7% | 65.0% | 90.7% | 87.4% |
| vlm_cheap | 97.1% | 100.0% | 96.9% | 99.1% |
| vlm_small | 70.0% | 60.2% | 87.3% | 83.9% |
| vlm_large | 98.7% | 100.0% | 99.3% | 100.0% |

Key fields = the ones that feed the Profile (net income, rent, cash). Costs as reported by OpenRouter.
Latency includes local OCR on a laptop CPU for the frugal strategies.
