# core/ handover (thread 1 → @llucliment)

Written by the previous owner (Juan's Claude, thread 1) on Sat 21 Nov 2026. Context for the change: UBS feedback, issue #21 and `docs/plan.md` ("UBS feedback at their booth (16:45) and the engine reframe"). For the model itself read `core/README.md`; this file is about where things live and how to change them safely.

## 1. Architecture map

Data flows top to bottom. Everything is a pure function: JSON-like dicts in, JSON-serialisable dicts out.

| File | Role | Key functions |
|---|---|---|
| `models.py` | Parse and validate input. `Profile`, `Liability`, `Goal`, `Intervention`. Resolves `{"assumption": id}` values. | `Profile.from_dict`, `parse_interventions`, `resolve_value` |
| `assumptions.py` | Assumption sets (defaults in `data/assumptions_ch.json`, tree extras in `data/trees/*.json`), overrides by id or param, a "zero world" set for the UBS starter kit. | `build_assumptions`, `AssumptionSet.with_overrides`, `.values()`, `zero_world_assumptions` |
| `schedule.py` | Profile + interventions → month-by-month **plan at today's prices** (income, rent, other, contributions, one-offs) and the **loan amortisation**. Interventions apply in order (child refines parent). | `build_schedule`, `debt_schedule` |
| `weather.py` | Named stresses → per-month arrays (inflation override, wage freeze, return shift/shock, job-loss multiplier, forced unemployment). Applied to the deterministic path too. | `build_weather`, `CATALOG` |
| `engine.py` | The monthly state transition, vectorised over paths. **`run_batch` runs K scenarios in one pass**, each with its own schedule and assumption values, sharing random draws. `run` = one scenario. With `stochastic=False` each scenario is exactly one deterministic path. | `run`, `run_batch`, `FLOW_KEYS` |
| `analysis.py` | Metrics from a run: goals, health score (components + weights), accounting checks, bands. | `evaluate_goals`, `health`, `checks`, `bands`, `first_negative` |
| `simulate.py` | One node → `SimulationResult` (deterministic run + Monte Carlo run + analysis + tornado). | `simulate_node`, `sensitivity_analysis`, `trace_id` |
| `tree.py` | Lazy tree: visible nodes, pruned ghosts, flattening interventions root → node, cache, and the API entry points. | `expand`, `simulate`, `node_info`, `assumptions_list`, `visible_nodes`, `pruned_nodes`, `flatten_interventions` |
| `starter.py` | Bridge to the UBS starter-kit format; reproduces its numbers exactly. | `simulate_starter` |
| `data/` | `assumptions_ch.json` (sourced defaults), `profiles/alexia.json`, `trees/alexia.json` (example content, still OPEN, proposal in PR #15). | |
| `examples/` | Real outputs used in `docs/contracts.md`. | `python -m core.examples.generate` |
| `tests/test_engine.py` | All engine tests. | |

**Public API used by `api/engine.py`** (thread 2): `core.expand(profile, path, assumptions, weather)`, `core.simulate(profile, node, assumptions, weather)`, `core.node_info(node_id)`, `core.assumptions_list(overrides)`, `core.weather_catalog()`. The adapter switches to core when `expand` and `simulate` exist. **Keep these signatures**; add keyword arguments with defaults if you need more.

## 2. Where to add new analyses

- **Per-node analysis** (break-even, goal-seek, …): write a function in a new `core/explore.py` that takes `(profile: Profile, interventions: list[dict], aset: AssumptionSet, weather)` like `sensitivity_analysis` does, and call it from `simulate_node` behind a flag. Put its output under a new additive key in the result (issue #21 suggests `exploration: {break_even, goal_seek, reverse_stress, timing}`).
- **Comparisons between nodes** (e.g. "when does the master's overtake working?") need two intervention lists. Get them with `tree.flatten_interventions(tree, node_id)`; `tree.expand` already has the results of the siblings in `results[...]` if you want to reuse them.
- **Fast many-scenario evaluation**: build K schedules + K assumption dicts and call `run_batch(..., stochastic=False)`. You get K deterministic paths in one vectorised pass (measured: 40 scenarios in ~10 ms). Use this for grid searches instead of looping `simulate_node` (which also runs Monte Carlo, analysis and rounding).
- **Text the engine produces** (e.g. `health.components[*].explanation`, `changes`): follow the new wording rule: "if… then…", "under these assumptions"; never "you will" / "expected".

## 3. Tests and examples

```bash
pip install numpy pytest
bash scripts/fetch_ubs_kit.sh                 # one test compares with the UBS code month by month (skipped without the kit)
python -m pytest core/tests api/tests -q      # run BOTH before merging: api/tests exercise core through the adapter
python -m core.examples.generate              # rewrites core/examples/*.json
```

- After regenerating examples, the **figures quoted in `docs/contracts.md`** (SimulationResult example) do not update themselves. Copy them from `core/examples/expand_alexia_2.json` (current node "2") or they drift.
- Timing tests use best-of-3 so a busy machine does not fail them.
- Contract changes (new or renamed fields) = update `docs/contracts.md` + board post tagging `@all` (thread 6 builds the UI, thread 2 the agent).

## 4. Pitfalls I know about

1. **Monte Carlo is wired into more than the bands.** `simulate_node` always runs MC, and `analysis.health` uses it for the `resilience` and `goals` components, `metrics` has `final_net_worth_p10/p50/p90`, `shortfall_probability`, `goal_probability`, and `checks` has `bands_ordered`. Making MC optional (issue #21) needs deterministic fallbacks for each of those (e.g. goals: met / not met on the deterministic path; resilience: deterministic first negative month), and the web/agent read some of these fields today.
2. **Indexing.** Stock series have H+1 points (index 0 = opening), flows have H points. Months are 0-based: `first_negative_month: 6` is "month 7" in the UI.
3. **Contributions are transfers.** Moving cash into investments does not change "liquid" wealth (cash + investments) except through returns, so a goal-seek on `monthly_investment_contribution` barely moves a liquid goal. Seek on income (`monthly_net_income` add) or spending (`monthly_other_expenses` add, negative) instead.
4. **Prices.** Planned amounts are at today's prices; the engine inflates expenses, one-offs and contributions, and grows income with inflation + real wage growth. A "break-even salary" found by search is therefore in today's CHF. Loan payments are nominal and fixed.
5. **Tax** is looked up on the planned (today's prices) annual income, times `income_tax_scale`. It is the least verified assumption (`verified: false`).
6. **Deterministic path = no random shocks** (no job loss, no unexpected expenses), so it is slightly more optimistic than the MC median. Weather events DO apply to it.
7. **Cache.** `tree._CACHE` keys on profile, interventions, assumptions, weather, seed, flags. If you add a parameter that changes results, add it to the key in `_cached_simulate`, or you will get stale results.
8. **Overrides.** `AssumptionSet.with_overrides` rebuilds from defaults plus previous user edits; the tornado only uses assumptions that declare a `range`. Tree-specific assumptions (salaries, tuition) live in the tree file and are merged after the defaults.
9. **Monotonicity for searches.** Final net worth and min cash are monotone in income, costs and one-offs, but only piecewise linear (tax brackets, interest on positive cash only, auto-liquidation of investments). Bisection works; closed forms are approximations.
10. **Loans.** No intervention can yet change an existing loan's payment or rate (extension B in `docs/tree-proposal.md`), and there are no node-level assumption overrides (extension A). Four proposed nodes need them.

## 5. Suggestions: deterministic "what would have to be true" analyses that fit the current code

All of these use only the deterministic path (`run`/`run_batch` with `stochastic=False`), so they are exact, reproducible and cheap.

1. **Break-even salary (master's vs working).** Find the post-master salary `s` such that `final_net_worth(node 2 | AS-alexia-master-salary = s) = final_net_worth(node 1)`. Grid of ~40 values in one `run_batch` (one schedule per value via `aset.with_overrides`), then interpolate; or bisection. Report "if the salary after the master's is at least CHF X (today's prices), then the master's ends ahead after 10 years". Variant without search: **crossover month** = first month where `net_worth(node 2)[t] >= net_worth(node 1)[t]`, read directly from the two deterministic series (`None` = never within the horizon).
2. **Goal-seek.** For each goal: the smallest monthly saving (as `monthly_other_expenses` add −x, see pitfall 3) or extra income that makes the deterministic liquid wealth at `goal.target_month + 1` reach `goal.target`. One batched grid, then interpolate. Also report the **earliest month the goal is reached** (already in `goals[*].first_reached_month_deterministic`).
3. **Reverse stress test.** "What breaks this plan first?" Three cheap measures:
   - **Largest affordable surprise expense** at month t: on the deterministic path, approximately `min over s >= t of (cash_s + investments_s)` (exact enough because flows are almost linear; confirm with one rerun adding `one_off_cost` of that size at t).
   - **Smallest income cut** (`monthly_net_income` × (1 − c)) that makes cash go negative: bisection on c in [0, 1].
   - **Longest job loss it survives**: increase the `job_loss` weather `duration_months` from a given start month until cash goes negative.
   Report as "if X happens, then cash runs out in month M".
4. **Timing / path dependence.** Same decision 12 or 24 months later: shift every month field of the node's own interventions by d (`from_month`, `to_month`, `month`, loan `start_month` and `payment_start_month`), keep the parent's plan for the first d months, compare final net worth, min cash and goal months. A small `shift_interventions(ivs, d)` helper in `explore.py` is enough; the existing schedule code handles the rest.
5. **Lever ranking without probabilities.** The tornado already ranks assumptions by swing; for a deterministic version, run it with `stochastic=False` in `run_batch` (one path per variant, ~10 ms for the whole tornado) and phrase it as "which assumption, moved within its sourced range, changes the outcome most".

Open items I leave behind: tree content (PR #15, waiting for Juan), extensions A and B, and the ⚠️ unverified figures listed in `docs/tree-proposal.md` and `data/assumptions_ch.json`.
