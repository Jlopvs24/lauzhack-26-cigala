# core/ — financial engine (thread 1)

Deterministic, tested engine behind every number in the app. Python 3.12 + numpy, pure functions, JSON in, JSON out. The LLM never computes: it only reads results produced here.

```bash
pip install numpy pytest
python -m pytest core/tests -q          # 26 tests: identities, edge cases, seeds, UBS starter kit, tree, weather
python -m core.examples.generate        # regenerate core/examples/*.json (real outputs, used in docs/contracts.md)
```

```python
import core
core.expand(profile, ["2", "2.2"], [{"id": "AS-alexia-master-tuition", "value": 8000}], ["recession"])
core.simulate(profile, {"node_id": "2"}, None, ["job_loss"])
```

Shapes: `docs/contracts.md` (v1). Tree content: `core/data/trees/alexia.json` (example, editable data). Default assumptions with sources: `core/data/assumptions_ch.json`.

## Model (monthly, 120 months)

State per path: cash `C`, investments `I` (one balanced portfolio), debts `D` (fixed-payment loans). Month `t`:

1. investment return `I·(G_t − 1)`; interest on positive cash;
2. cash flows: + net income − income tax − living expenses (rent + other) − one-off costs + one-off income − loan payments + new loans;
3. planned investment contribution moved from cash to investments if cash allows (a transfer: net worth unchanged);
4. if cash < 0, investments are sold to cover it (`AS-auto-liquidate`); remaining negative cash = unfunded financing need (UBS starter-kit convention), flagged in `first_negative_month` / `shortfall_probability`.

Identities verified on every run and returned in `checks`: cash flow, net-worth change, balance sheet (`NW = C + I − D`), investment account, no negative debt/investments, ordered bands, every assumption sourced.

## Uncertainty (Monte Carlo, per visible node)

1,000 paths, seed 42, vectorised over paths (~55 ms per node). Random: annual inflation (normal, clipped), monthly portfolio returns (lognormal with the stated mean/volatility), job loss (monthly hazard from the annual probability, geometric spell length, income replaced by unemployment insurance), unexpected expenses (Poisson-like, exponential size). The deterministic path uses central values and no random shocks. Shocks are independent (no correlation between inflation, returns and job loss) — a stated simplification.

## Simplifications (documented on purpose)

- **Income tax**: one effective-rate table (single person, Lausanne, from the ESTV calculator) applied to annualised income at today's prices (no bracket creep). Incomes are net of social contributions; wealth tax, deductions, church tax and pillar 2/3a are ignored.
- Inflation applies to all planned expenses, one-offs and contributions; wages grow at inflation + real wage growth. Loan payments are fixed nominal amounts. Monthly loan rate = annual / 12.
- One currency (CHF); "move abroad" amounts are already converted at a constant exchange rate.
- Non-financial assets (car, property) are not modelled: buying a car is a cost.
- Unemployment insurance applies to any income, including student jobs (in reality students without 12 months of contributions get nothing — editable via `AS-unemployment-replacement`).
- Health score weights (liquidity 0.3, goals 0.3, debt 0.2, resilience 0.2) are a value judgement, returned with each score.

## Files

| File | What |
|---|---|
| `models.py` | input parsing/validation (Profile, Intervention) |
| `assumptions.py` | assumption sets, overrides, zero-world set for the starter kit |
| `schedule.py` | profile + interventions → monthly plan; loan amortisation |
| `engine.py` | vectorised monthly state transition |
| `weather.py` | recession / inflation / market crash / job loss |
| `analysis.py` | metrics, goals, health, accounting checks |
| `simulate.py` | one node → SimulationResult, sensitivity tornado |
| `tree.py` | lazy tree with pruning, `expand`, `simulate` |
| `starter.py` | UBS starter-kit bridge (reproduces its results exactly) |
