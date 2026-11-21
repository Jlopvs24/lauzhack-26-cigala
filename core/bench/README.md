# core/bench — calibration and benchmark harness (#42)

```bash
bash scripts/fetch_ubs_kit.sh   # once: the private UBS kit into vendor/ubs-kit (gitignored)
python -m core.bench            # report: public targets, ledger consistency, implied params, replay, drift
python -m core.bench --json     # same as JSON
python -m pytest core/tests/test_bench.py -q   # UBS-data tests skip without the kit
```

| piece | what it does |
|---|---|
| `ubs.load()` | UBS synthetic data (profiles, ledger, goals, assets, liabilities, scenario assumptions, life events, transactions aggregated per profile/month/category), stdlib + numpy only |
| `harness.ledger_consistency()` | the ledgers' own identities: opening + net = closing, months chain, transactions sum to the net |
| `harness.implied_parameters()` | what the synthetic generator implies (salary and cost growth, surprise expenses, bonuses) next to our assumptions |
| `harness.replay(world="zero"\|"swiss", overrides=...)` | every UBS profile through our engine for its 24 ledger months with its average budget; error in months of budget |
| `harness.drift_decomposition()` | where our Swiss world departs from the ledgers, switching tax, inflation and wage growth off one by one |
| `harness.score(overrides, include=("verified",))` | a parameter set against PUBLIC Swiss targets (`targets.json`), squared error in tolerance units |
| `harness.search(grid)` | exhaustive grid over assumption ids, ranked by `score` |

Rules for using it (Juan's direction): the UBS ledgers are a **sanity check** of accounting and
consistency; never tune the model to them (they are synthetic and contain no income tax).
Tune only against public sources: fill the `to_fill` targets and check the `to_verify` ones
from `SOURCES.md`, then `score` / `search`. Contribution rates, thresholds and rules of thumb
are never optimised, only sourced or labelled. Only aggregates of the UBS data are printed;
the kit itself must never be committed.
