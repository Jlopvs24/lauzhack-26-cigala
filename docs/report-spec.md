# Branch headlines, plan check and the path report (spec, DECIDED 17:40)

Grounded in a full review of the UBS kit (`vendor/ubs-kit`). Weights are the kit's draft rubric (`evaluation/judge-scorecard.md`, `faq/submission-and-judging.md` Q8): modelling correctness 25 · scenario/counterfactual exploration 20 · technical execution & validation 15 · UX & communication 15 · innovation 15 · responsible design & transparency 10. Judges ask: which assumptions matter most, how a decision changes the state, how you verified it, **what happens when a constraint is violated**, what you would improve next.

## 1. Branch card headline (no more "cash" everywhere)

The kit's per-scenario metrics are "liquidity, net worth, goal feasibility, constraint breaches" (`Data/scenario-catalog.csv`). Each card has two slots, computed by the engine as `result.headline = {slot_a, slot_b, metric_key}` so the web and Lumi say the same thing:

- **Slot A — "Does it hold?"** first that applies: (1) funding gap: "Funding gap CHF |min_cash| from month first_negative_month+1"; (2) a missed goal: "<goal> missed by CHF x"; (3) else "Tightest buffer: N months (month m)".
- **Slot B — "What it trades"**: the metric that differs most from its siblings (normalised gap vs sibling median over sibling spread) among real final net worth, min cash, liquidity months, final debt, earliest goal reached; plus the matching `delta_vs_parent` as "vs before this choice".

## 2. Health → "Plan check"

- **Feasibility first**: any funding gap or breached constraint makes the level `infeasible` / "needs financing", whatever the score (`scenario-modelling.md` §4).
- **Constraints dashboard**: `result.constraints[]` with name, threshold, user- or scenario-defined, passed, margin, first breach month, months in breach (liquidity floor, debt-service limit DS/Y ≤ d_max, goals).
- Replace the 0/1 "resilience" with deterministic resilience: shock buffer (`exploration.reverse_stress.value`) and/or "holds in N of 4 weather scenarios".
- Debt becomes pass/fail with margin (a loan that closes a gap must not look worse).
- If a single score is kept, it is secondary, weights visible, renamed "Plan check". Never imply the highest net worth is best (`faq/financial-modelling.md` Q17).

## 3. Path report ("Open your report" at a leaf) — `POST /report {profile, path, assumptions}`

No LLM-generated numbers; the plain-language summary is generated from these fields and checked against them.

1. Plain-language summary ("if… then…", never advice).
2. Question and scope: horizon, currency, jurisdiction, as_of, nominal vs real, the question.
3. Starting state with provenance per field, labelled synthetic / observed / user-entered.
4. Each decision on the path: what it changed, interventions, the assumptions it introduces (kind, source, verified), delta vs parent, events, debts, explanation.
5. Baseline vs alternatives at every level (chosen vs siblings, plus a status-quo baseline): real net worth, lowest cash, goals met, debt. Pruned siblings are simulated for the report.
6. Exploration per step: levers, break-even, goal-seek, reverse stress, timing, tornado.
7. Stress scenarios: the leaf under none / recession / inflation / market crash / job loss, side by side.
8. Constraints and breaches (from §2), including length of the funding gap and monthly surplus.
9. Non-financial trade-offs (flexibility, education, location), qualitative and labelled as such.
10. Optional uncertainty lens: bands with seed and path count, "not real-world probabilities".
11. Validation and reproducibility: checks, seed, engine_version, trace_id, a "reproduce" payload, isolation and monotonicity test evidence.
12. Limitations and responsible-AI statement: synthetic data, simplifications, not a forecast, not advice, how invented claims are prevented.

Ownership: engine fields (headline, constraints, plan check, per-step exploration, stress side-by-side) → Lluc (`core/`); `/report` aggregation + checked summary → thread 2 (`api/`); report UI + cards → thread 6 (`web/`).
