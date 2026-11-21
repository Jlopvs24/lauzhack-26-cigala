# core/ — financial engine (thread 1)

Deterministic, tested engine behind every number in the app. Python 3.12 + numpy, pure functions, JSON in, JSON out. The LLM never computes: it only reads results produced here.

```bash
pip install numpy pytest
python -m pytest core/tests -q          # identities, edge cases, seeds, UBS starter kit, tree, weather, exploration
python -m core.examples.generate        # regenerate core/examples/*.json (real outputs, used in docs/contracts.md)
```

```python
import core
core.expand(profile, ["2", "2.2"], [{"id": "AS-alexia-master-tuition", "value": 8000}], ["recession"])
core.simulate(profile, {"node_id": "2"}, None, ["job_loss"])               # deterministic + exploration
core.simulate(profile, {"node_id": "2"}, None, None, uncertainty=True)     # adds the optional Monte Carlo lens
```

## Exploration first (issue #21)

Every result is first a deterministic "if these inputs hold, then..." path under visible assumptions. On top of it, `explore.py` answers "what would have to be true" questions by re-running the same engine with one input moved (`result.exploration`, current node only):

- **levers**: the assumptions that move this node most (deterministic tornado); any of them can be overridden per request.
- **break-even**: against each sibling, the month this branch gets and stays ahead, and the value of its income assumption at which both branches end level.
- **goal-seek**: the extra monthly income needed to meet each dated goal.
- **reverse stress**: the smallest one-off cost in month 0 that makes cash negative or misses a goal.
- **timing**: the same decision 12 or 24 months later (path dependence).

Method limits: thresholds come from a 9-point grid then bisection to 0.01, assuming the margin increases with the lever (otherwise `non_monotone` and no value); income/cost searches stop at CHF 1,000,000; goal-seek income starts in month 0 and is indexed like other income; reverse-stress costs fall in month 0. Weather scenarios stay named deterministic what-ifs.

Shapes: `docs/contracts.md` (v1). Tree content: `core/data/trees/alexia.json` (example, editable data). Default assumptions with sources: `core/data/assumptions_ch.json`.

## Model (monthly, 120 months)

State per path: cash `C`, investments `I` (one balanced portfolio), debts `D` (fixed-payment loans). Month `t`:

1. investment return `I·(G_t − 1)`; interest on positive cash;
2. cash flows: + net income − income tax − living expenses (rent + other) − one-off costs + one-off income − loan payments + new loans;
3. planned investment contribution moved from cash to investments if cash allows (a transfer: net worth unchanged);
4. if cash < 0, investments are sold to cover it (`AS-auto-liquidate`); remaining negative cash = unfunded financing need (UBS starter-kit convention), flagged in `first_negative_month` / `shortfall_probability`.

Identities verified on every run and returned in `checks`: cash flow, net-worth change, balance sheet (`NW = C + I − D`), investment account, no negative debt/investments, ordered bands (lens on only), every assumption sourced.

## Optional uncertainty lens (Monte Carlo, off by default)

Only with `uncertainty=True`: 1,000 paths, seed 42, vectorised over paths (~50-90 ms per node). Results stay conditional on the assumptions: shares of simulated paths, not real-world probabilities. The tornado is deterministic (one batched pass). Random: annual inflation (normal, clipped), monthly portfolio returns (lognormal with the stated mean/volatility), job loss (monthly hazard from the annual probability, geometric spell length, income replaced by unemployment insurance), unexpected expenses (Poisson-like, exponential size). The deterministic path uses central values and no random shocks. Shocks are independent (no correlation between inflation, returns and job loss) — a stated simplification.

## Simplifications (documented on purpose)

- **Income tax** (#48 item 3, `core/tax.py`): official ESTV 2026 effective rates (federal + cantonal + communal, standard deductions, no church tax) for the profile's `city` (12 cities) or `canton`, as `single` / `couple` (married, one earner) / `family` (two children); unknown places are taxed as Lausanne and flagged (`tax_residence[].fallback`). A node can move the residence (`tax_residence` intervention); abroad is one flat assumed rate (`AS-tax-abroad-rate`, unverified). Applied to annualised income at today's prices (no bracket creep), paid in the same month (no arrears). Incomes are net of social contributions; wealth tax, church tax, own deductions and pillar 3a are ignored. `profile.income_basis` says whether incomes are before income tax (`net_before_tax`, default, tax charged) or take-home (`take_home`, no tax charged; used for imported UBS profiles).
- **Payroll** (#48 item 2, `core/payroll.py`): a profile or node may give `monthly_gross_income` instead of a net salary; employee AHV/IV/EO, ALV and NBU (to the insured-salary cap) and half the BVG age credit are deducted (2026 rates, `payroll_*` assumptions). `core.payslip(gross, age)` shows one month. The BVG balance is reported in `payroll`, not counted in net worth. Thresholds move with the wage index; men's age bands; one employer; no BVG risk premiums.
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
| `explore.py` | levers, break-even, goal-seek, reverse stress, timing (deterministic) |
| `plan.py` | constraints, plan check (feasibility first), weather resilience, branch headlines |
| `report.py` | `report_data`: every number of the path report |
| `tree.py` | lazy tree with pruning, `expand`, `simulate` |
| `starter.py` | UBS starter-kit bridge (reproduces its results exactly) |
