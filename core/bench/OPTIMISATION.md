# Parameter optimisation against public targets (#48 item 8)

The fit uses verified targets with positive weights. The two balanced-return approximations are retained as illustrative references with weight zero. Pictet publishes individual asset geometric returns. Computing a portfolio CAGR requires a portfolio series or an appropriate estimator. The 0.5 percentage-point cost deduction remains a team modelling choice.

The search keeps the existing defaults after the materiality and leave-one-target-out checks. Real wage growth remains at 1% because the two source windows produce conflicting directions.

## Reproduce

```bash
python -m core.bench.optimise
python -m core.bench.optimise --json
python -m pytest core/tests/test_optimise.py -q
```

## Method

The command uses 400 seeded random candidates followed by four rounds of coordinate refinement within the declared ranges. Payroll rates, tax rules and value judgements are excluded from the search. A proposed change needs a loss reduction of at least 0.25 and a consistent direction under leave-one-target-out fits. A parameter informed by one target needs a gain of at least 1.0. Tolerances and weights are modelling choices and should be inspected alongside the sources.

The regression checks cover fixed-seed reproducibility, range bounds, rule and illustrative-target exclusion, acceptance of a material single-target change, rejection of a small gain, and rejection when the source windows reverse direction.

## Regenerated results

The following tables are the command output. Month indices are zero-based.

loss over 15 verified targets with weight > 0 (16 scored): before item 7 2.2267, defaults 2.2089, best fit 1.2442, chosen 2.2089 (seed 20261121, 400 samples + 4 refinement rounds)

| target | public value | tolerance | weight | model (defaults) | loss (defaults) | model (best fit) | loss (best fit) |
|---|---|---|---|---|---|---|---|
| `cpi-recent-average` | 0.0113 | 0.005 | 1 | 0.01 | 0.0676 | 0.01117 | 0.0007 |
| `cpi-recent-sd` | 0.0095 | 0.005 | 0.5 | 0.008 | 0.045 | 0.008 | 0.045 |
| `snb-price-stability` | 0.01 | 0.01 | 0.5 | 0.01 | 0.0 | 0.01117 | 0.0068 |
| `real-wage-recent` | 0.0115 | 0.006 | 0.5 | 0.01 | 0.0312 | 0.00494 | 0.5977 |
| `real-wage-5y` | -0.0016 | 0.006 | 0.5 | 0.01 | 1.8689 | 0.00494 | 0.594 |
| `savings-rate` | 0.0011 | 0.001 | 1 | 0.001 | 0.01 | 0.0011 | 0.0 |
| `unemployment-rate` | 0.0295 | 0.01 | 0 | 0.03 | 0.0 | 0.03499 | 0.0 |
| `unemployment-inflow` | 0.035 | 0.01 | 0.5 | 0.03 | 0.125 | 0.03499 | 0.0 |
| `uv-replacement` | 0.7 | 0.05 | 1 | 0.7 | 0.0 | 0.7 | 0.0 |
| `uv-duration` | 5.8 | 1.5 | 1 | 5.8 | 0.0 | 5.8 | 0.0 |
| `balanced-vol` | 0.107 | 0.02 | 0.5 | 0.1 | 0.0612 | 0.107 | 0.0 |
| `ahv-iv-eo-employee` | 0.053 | 0.001 | 1 | 0.053 | 0.0 | 0.053 | 0.0 |
| `alv-employee` | 0.011 | 0.001 | 1 | 0.011 | 0.0 | 0.011 | 0.0 |
| `bvg-entry-threshold` | 22680 | 100 | 1 | 22680.0 | 0.0 | 22680.0 | 0.0 |
| `bvg-coordination-deduction` | 26460 | 100 | 1 | 26460.0 | 0.0 | 26460.0 | 0.0 |
| `pillar-3a-max` | 7258 | 1 | 1 | 7258.0 | 0.0 | 7258.0 | 0.0 |

| parameter | sourced default | range | targets | best fit | leave-one-out best fits | loss gain (needed) | robust | chosen |
|---|---|---|---|---|---|---|---|---|
| `AS-inflation-mean` | 0.01 | [0.0, 0.03] | 2 | 0.01117 | 0.01 to 0.01131 | 0.0601 (0.25) | no: side changes without cpi-recent-average | 0.01 (kept) |
| `AS-real-wage-growth` | 0.01 | [0.0, 0.02] | 2 | 0.00494 | 0.00259 to 0.0115 | 0.7084 (0.25) | no: side changes without real-wage-5y | 0.01 (kept) |
| `AS-investment-vol` | 0.1 | [0.05, 0.12] | 1 | 0.107 | 0.1 to 0.1 | 0.0612 (1.0) | one source | 0.1 (kept) |
| `AS-cash-interest` | 0.001 | [0.0, 0.01] | 1 | 0.0011 | 0.001 to 0.001 | 0.01 (1.0) | one source | 0.001 (kept) |
| `AS-job-loss-prob` | 0.03 | [0.01, 0.08] | 1 | 0.03499 | 0.03 to 0.03 | 0.125 (1.0) | one source | 0.03 (kept) |
| `AS-unemployment-duration` | 5.8 | [3.0, 12.0] | 1 | 5.8 | 5.8 to 5.8 | 0.0 (1.0) | one source | 5.8 (kept) |

| node | set | final net worth | at today's prices | min cash | first negative month | plan check |
|---|---|---|---|---|---|---|
| 0 Today: student in Lausanne | defaults | -22,056 | -19,967 | -22,056 | 27 | needs_financing |
| 0 Today: student in Lausanne | best_fit | -26,239 | -23,480 | -26,239 | 26 | needs_financing |
| 0 Today: student in Lausanne | chosen | -22,056 | -19,967 | -22,056 | 27 | needs_financing |
| 0 Today: student in Lausanne | real_wage_0.5pct | -25,996 | -23,534 | -25,996 | 26 | needs_financing |
| 0 Today: student in Lausanne | real_wage_2pct | -13,834 | -12,524 | -13,834 | 29 | needs_financing |
| 1 Start working | defaults | 125,605 | 113,708 | 8,736 | None | holds_below_target |
| 1 Start working | best_fit | 113,835 | 101,867 | 8,737 | None | holds_below_target |
| 1 Start working | chosen | 125,605 | 113,708 | 8,736 | None | holds_below_target |
| 1 Start working | real_wage_0.5pct | 113,299 | 102,568 | 8,736 | None | holds_below_target |
| 1 Start working | real_wage_2pct | 151,280 | 136,952 | 8,736 | None | holds_below_target |
| 2 Do a master's | defaults | 113,330 | 102,596 | -18,553 | 6 | needs_financing |
| 2 Do a master's | best_fit | 100,719 | 90,130 | -18,721 | 6 | needs_financing |
| 2 Do a master's | chosen | 113,330 | 102,596 | -18,553 | 6 | needs_financing |
| 2 Do a master's | real_wage_0.5pct | 100,045 | 90,569 | -18,692 | 6 | needs_financing |
| 2 Do a master's | real_wage_2pct | 141,076 | 127,714 | -18,275 | 6 | needs_financing |
| 3 Move abroad | defaults | 53,065 | 48,039 | 1,746 | None | infeasible |
| 3 Move abroad | best_fit | 42,850 | 38,345 | 1,746 | None | infeasible |
| 3 Move abroad | chosen | 53,065 | 48,039 | 1,746 | None | infeasible |
| 3 Move abroad | real_wage_0.5pct | 42,705 | 38,660 | 1,746 | None | infeasible |
| 3 Move abroad | real_wage_2pct | 74,681 | 67,608 | 1,746 | None | holds_below_target |

## Limits

The target set is small and several parameters depend on a single source. The selection filters express explicit modelling policies. The SECO duration measures elapsed current unemployment spells. The inflow target annualises one seasonally high month. Wage windows overlap and describe economy-wide averages. Historical return references and chosen cost deductions require further evidence before they enter the fitting objective. The synthetic UBS ledgers remain accounting checks.
