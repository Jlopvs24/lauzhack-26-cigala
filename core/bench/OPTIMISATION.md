# Parameter optimisation against public targets (#48 item 8)

```bash
python -m core.bench.optimise          # reproduces every table below (about 5 s, fixed seed)
python -m core.bench.optimise --json
```

## Result

**No default moves.** The defaults are already the best defensible set: every tunable parameter
sits within half a tolerance of what the public sources say, or the sources disagree with each
other about the direction. The one data-driven correction of the session, the unemployment duration
(6 → 5.8 months, SECO), landed with the verification pass (#48 item 7).

| parameter set | loss (16 verified targets) |
|---|---|
| defaults before item 7 | 2.3459 |
| **defaults now = chosen set** | **2.3281** |
| unconstrained best fit inside the sourced ranges | 1.2442 |

The best fit would cut the loss by 1.08, and 0.71 of that comes from one parameter, real wage growth
(1.0% → 0.5%). That move is rejected by the robustness guard, for a reason worth reading (below).

## Method

- **Objective.** `harness.score`: weighted squared error in tolerance units over the entries of
  `targets.json` with `status: "verified"` and weight > 0. A tolerance is the target's own
  uncertainty (a standard error where one can be computed), so a loss of 1 means "one tolerance away".
- **Targets.** Public Swiss sources only, each read on the primary page. The UBS synthetic ledgers are
  not a target: they stay a consistency smoke check (`python -m core.bench`).
- **Searched.** The parameters tagged `tunable` in `params.json` that have a sourced `range` and at
  least one target: 7 of them. Each stays inside its range.
- **Search.** 400 seeded random points (seed 20261121), then 4 rounds of coordinate refinement in a
  shrinking window. The objective is smooth and nearly separable, so this is more than enough; one fit
  takes about 0.3 s.
- **Overfitting guards.** With 9 informative targets for 7 parameters, a fit can chase noise. A parameter leaves
  its sourced default only if the move is:
  1. **material**: it lowers the loss by at least 0.25, i.e. the default is more than half a tolerance
     from what the targets say; and
  2. **robust**: with two or more targets on the parameter, the best fit stays on the same side of
     the default when any one of them is left out (leave-one-target-out). With a single target that
     test is impossible, so the bar is a gain of at least 1.0 (more than one full tolerance).

## Targets

| target | public value | tolerance | weight | model | loss | source |
|---|---|---|---|---|---|---|
| `cpi-recent-average` | 1.13% | 0.5 | 1 | 1.0% | 0.068 | FSO CPI 2023-2025 |
| `cpi-recent-sd` | 0.95% | 0.5 | 0.5 | 0.8% | 0.045 | same three FSO figures (3 observations) |
| `snb-price-stability` | 1.0% | 1.0 | 0.5 | 1.0% | 0 | SNB: price stability = CPI below 2%; midpoint of 0-2% |
| `real-wage-recent` | +1.15% | 0.6 | 0.5 | 1.0% | 0.031 | FSO wage index 2024-2025 |
| `real-wage-5y` | −0.16% | 0.6 | 0.5 | 1.0% | **1.869** | FSO wage index 2021-2025 (−0.8, −1.9, −0.4, +0.7, +1.6) |
| `savings-rate` | 0.11% | 0.1 | 1 | 0.10% | 0.010 | Moneyland, average savings account |
| `unemployment-inflow` | 3.5%/yr | 1.0 | 0.5 | 3.0% | 0.125 | SECO Dec 2024, table 7: registrations from employment |
| `uv-duration` | 5.8 months | 1.5 | 1 | 5.8 | 0 | SECO Dec 2024, table 5 |
| `uv-replacement` | 70% | 5 | 1 | 70% | 0 | unemployment insurance (rule, not searched) |
| `balanced-real-return` | 3.35% real | 1.1 | 1 | 2.97% | 0.119 | Pictet 1926-2024: real 5.6% shares, 2.1% bonds → 50/50 = 3.85%, minus 0.5 of costs |
| `balanced-vol` | 10.7% | 2 | 0.5 | 10% | 0.061 | Pictet: SD 19.9% / 3.9%, correlation 28% → 50/50 |
| 5 payroll and 3a rules | exact | | 1 | exact | 0 | BSV, BVV 3: regression guards, never searched |

Reported, not in the objective (weight 0):

- `unemployment-rate` (2.95%): a stock rate, not the hazard the engine needs. `unemployment-inflow`
  replaces it.
- `balanced-return` (5.35% nominal): the 1926-2024 nominal returns carry that period's 2% average
  inflation, the model assumes 1%. The like-for-like comparison is in real terms: the model's
  (1 + 4%) / (1 + 1%) − 1 = 2.97% against 3.35%, a third of a tolerance. The nominal default looked
  a full point low; in real terms it is not.
- `tax-lausanne-*`: matched by construction since the tax tables are the ESTV figures (#48 item 3).

## Parameters

| parameter | sourced default | range | targets | best fit | leave-one-out best fits | loss gain (needed) | robust | chosen |
|---|---|---|---|---|---|---|---|---|
| `AS-inflation-mean` | 1.0% | 0-3% | 3 | 1.11% | 0.94% to 1.13% | 0.07 (0.25) | no: side changes without `cpi-recent-average` | 1.0% (kept) |
| `AS-real-wage-growth` | 1.0% | 0-2% | 2 | 0.49% | 0.26% to 1.15% | 0.71 (0.25) | **no: side changes without `real-wage-5y`** | 1.0% (kept) |
| `AS-investment-return` | 4.0% | 1-7% | 1 | 4.5% | n/a | 0.20 (1.0) | one source | 4.0% (kept) |
| `AS-investment-vol` | 10% | 5-12% | 1 | 10.7% | n/a | 0.06 (1.0) | one source | 10% (kept) |
| `AS-cash-interest` | 0.10% | 0-1% | 1 | 0.11% | n/a | 0.01 (1.0) | one source | 0.10% (kept) |
| `AS-job-loss-prob` | 3.0% | 1-8% | 1 | 3.5% | n/a | 0.13 (1.0) | one source | 3.0% (kept) |
| `AS-unemployment-duration` | 5.8 | 3-12 | 1 | 5.8 | n/a | 0 (1.0) | one source | 5.8 (kept) |

**Real wage growth is the only material candidate, and the data does not agree on its direction.**
The last two years say +1.15%, the last five say −0.16% (they include the 2022 inflation shock). A
fit lands in the middle at 0.5%; drop the five-year window and it asks for 1.15%, drop the two-year
window and it asks for 0.26%. Which window is "right" is a judgement, not a measurement, so the
default stays at 1.0%, inside the sourced range, and the parameter stays a visible lever (it is in
the tornado and can be overridden per request).

There is a second reason not to lower it: both targets are economy-wide averages. The person in the
demo is 20. The FSO wage survey 2024 shows the median wage about 25% higher at 30-39 than at 20-29
(about 2.3% a year on top of the general level), and university master's graduates went from about
CHF 78,000 to CHF 95,000 in their first five years (FSO graduate survey, 2014 cohort). For a young
profile 1.0% is already on the prudent side.

## How the tree's headline numbers move

10-year final net worth (nominal CHF), funding gap or lowest cash, and plan check.

| node | defaults = chosen | best fit (not adopted) | real wage 0.5% | real wage 2% |
|---|---|---|---|---|
| 0 Today: student in Lausanne | −22,056 · gap from month 28 | −26,233 · month 27 | −25,996 | −13,834 |
| 1 Start working | 125,605 · holds below target | 113,819 · same | 113,299 | 151,280 |
| 2 Do a master's | 113,330 · gap 18,553 from month 7 | 100,699 · gap 18,720 | 100,045 | 141,076 |
| 3 Move abroad | 53,065 · infeasible | 42,843 · same | 42,705 | 74,681 · holds below target |

What this shows:

- **The decisions do not depend on the calibration.** The ranking 1 > 2 > 3, the master's funding
  gap (CHF 18.6k from month 7) and every plan check are the same under the defaults and under the
  best fit.
- **The level does**: 10-year net worth moves by about 10% between the two sets, almost all of it
  from real wage growth (compare "best fit" with "real wage 0.5%"). From 0.5% to 2% the same
  decision ends between CHF 113k and 151k. Wage growth is the parameter to show and discuss, not to
  hide in a default.
- **One headline is knife-edge**: "Move abroad" is infeasible by a single goal missed by about
  CHF 500; at 2% wage growth it holds. The UI already says by how much the goal is missed.

## Deliberately not optimised

| what | why |
|---|---|
| Payroll rates and thresholds, pillar 3a caps, tax tables | legal rules, verified to the franc; they are regression guards in the objective, never searched |
| `AS-liquidity-target`, `AS-debt-service-limit`, `AS-auto-liquidate`, health-score weights | value judgements and engine rules; labelled, not fitted |
| `AS-unexpected-prob`, `AS-unexpected-mean` | no public target exists (the FSO budget survey has no such line). The UBS synthetic data implies 0.83 surprises a year of CHF 950, but fitting to it is exactly what we must not do |
| `AS-inflation-sd` | no sourced range; its one target (3 observations) is within a third of a tolerance |
| Anything against the UBS ledgers | synthetic data with no income tax line; kept as an accounting smoke check only |
| Weather intensities | scenario definitions, not estimates |
| Tree assumptions (salaries, rents, tuition) | verified or labelled one by one in item 7; they are scenario inputs the user edits, not parameters to fit |

## Known limits of this exercise

- Few targets: 9 informative ones for the 7 searched parameters, and 5 parameters rest on a single source. The
  guards are what keep that from becoming curve fitting.
- `uv-duration` is the elapsed duration of current spells. A stock-flow check with the same SECO
  report (112,563 unemployed, about 32,600 registrations a month) gives completed spells of about
  3.5 months at December's inflow (a seasonally high month, so somewhat longer over a year): 5.8 is
  on the prudent side.
- `unemployment-inflow` uses one seasonally high month; a full-year inflow would make it a weight-1
  target.
- The return target is historical. Swiss bond yields are now far below the 4.0% of 1926-2024, which
  is why the default stays below the historical figure and was not moved up.
- An age-dependent wage profile would be a better model than one growth rate for all ages. It is a
  model change, not a parameter fit, and is not done here.
