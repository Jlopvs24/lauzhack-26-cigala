# Shared contracts (v0 — draft)

Owned by the coordination thread. Changing anything here = PR + board post tagging @all. Thread 1 (engine) proposes v1 by Sat 15:00.

Conventions: money in CHF as numbers (2 decimals), months indexed 0..119 from the profile's `as_of` date, rates as decimals (0.05 = 5%), all JSON keys snake_case.

## Profile (roots) — produced by questionnaire or multimodal extraction

```json
{
  "profile_id": "P00001",
  "display_name": "Alexia",
  "age": 20,
  "city": "Lausanne",
  "currency": "CHF",
  "as_of": "2025-01-01",
  "employment_status": "student",
  "cash": 8000,
  "monthly_net_income": 1200,
  "monthly_rent": 900,
  "monthly_other_expenses": 600,
  "assets": [{"type": "investment", "value": 0}],
  "liabilities": [{"type": "student_loan", "principal": 0, "annual_rate": 0.0, "monthly_payment": 0}],
  "goals": [{"name": "Emergency savings", "target": 12800, "target_date": "2029-12-31", "priority": "high"}],
  "provenance": {"monthly_net_income": {"source": "payslip_ocr", "confidence": 0.97}}
}
```

`provenance` records where each field came from (questionnaire, voice, document + extractor, user edit).

## Decision node (branch)

```json
{
  "node_id": "1.1",
  "parent_id": "1",
  "label": "Master's, full time, with scholarship",
  "interventions": [{"param": "monthly_net_income", "op": "set", "value": 0, "from_month": 0, "to_month": 24}],
  "assumptions_ref": ["AS-tuition-epfl-2025"],
  "status": "chosen | sibling | child | pruned"
}
```

## Assumption

```json
{"id": "AS-tuition-epfl-2025", "param": "annual_tuition", "value": 1460, "unit": "CHF/year",
 "source": "https://...", "retrieved": "2026-11-21", "editable": true, "kind": "assumption | observation"}
```

## Simulation result (per node)

```json
{
  "node_id": "1.1",
  "seed": 42,
  "n_paths": 1000,
  "horizon_months": 120,
  "deterministic": {"cash": [8000, 7322.45], "net_worth": [8000, 7322.45]},
  "bands": {"net_worth": {"p10": [], "p50": [], "p90": []}},
  "metrics": {"final_net_worth_p50": 0, "min_cash": 0, "first_negative_month": null,
              "goal_probability": {"Emergency savings": 0.0}, "liquidity_months": 0},
  "health": {"score": 0.0, "components": {"liquidity": 0.0, "debt": 0.0, "goals": 0.0}},
  "sensitivity": [{"assumption_id": "AS-...", "delta_final_net_worth": 0}],
  "checks": [{"name": "cash_flow_identity", "passed": true}],
  "trace_id": "sim-..."
}
```

## API (thread 2) — draft routes

| Method | Route | Purpose |
|---|---|---|
| POST | `/profiles/extract` | multipart files/audio/text → Profile + provenance + cost/latency |
| POST | `/tree/expand` | `{profile, path, assumptions}` → visible nodes (path, siblings, children) with SimulationResults |
| POST | `/simulate` | `{profile, node, assumptions, weather}` → SimulationResult |
| POST | `/agent/ask` | `{question, context}` → answer + tool traces (numbers only from engine) |
| POST | `/voice/stt`, `/voice/tts` | speech in/out |

## Env vars

| Name | Used by | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | api, multimodal | AXA key, USD 10 budget: log cost per call |
| `TOGETHER_API_KEY` | api, multimodal | organizers' key |
