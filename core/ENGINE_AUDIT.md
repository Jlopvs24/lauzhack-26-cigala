# Engine audit (#42): what the engine does, where a UBS judge could attack it, what to improve

Prepared for the evening maths session (Juan + Lluc). Scope: `core/` on master after #40
(`core-1.1`). This is an honest audit: every weakness below is real in the current code.
Companion files: `core/bench/` (calibration and benchmark harness, `python -m core.bench`)
and `core/bench/SOURCES.md` (public Swiss sources to verify the `verified: false` figures).

Judging weights (UBS draft rubric): modelling correctness 25 · scenario/counterfactual
exploration 20 · technical execution & validation 15 · UX & communication 15 · innovation 15 ·
responsible design & transparency 10. Direction for tonight: make the simulation and
exploration more correct and richer; never predict, never fit the model to the synthetic data.

## 1. What the benchmark says today

`python -m core.bench` (needs the private UBS kit, see `core/bench/README.md`):

| check | result |
|---|---|
| UBS ledger identities (opening + net = closing, months chain, transactions sum to the net) | pass on 1,200 profiles × 24 months, max error CHF 0.00 |
| Replay of every UBS profile through our engine, cash-only world, same average budget | smoke check only: the budget is each profile's own 24-month average, so the final cash matches by construction (median error 0.00); the month-by-month gap (0.22 months of budget) is only the timing of their irregular items |
| Same replay in our Swiss default world | median −3.0 months of budget after 24 months (p10 −4.5, p90 −1.2) |
| Drift decomposition | income tax explains all of it: without income tax +0.36; also without inflation +0.26; also without wage growth +0.03 |
| Public targets | verified only: loss 0.14 over 4 targets (none beyond 0.3 tolerance units); verified + to_verify: 0.64 over 7, the balanced return (to verify) being 1 tolerance below its target |
| UBS scenario assumptions (the only two in the kit) | tuition: UBS Alexia CHF 8,000/yr (median over profiles 4,800) vs ours 2,500 (range 1,560-8,000: the UBS figure is our high end); study duration 2 years in both |

What the synthetic generator implies, next to our assumptions (a sanity reference, not a target):

| quantity | UBS synthetic | ours |
|---|---|---|
| salary growth year 2 vs year 1 | +1.2% | +2.0% (inflation 1% + real wages 1%) |
| recurring non-rent spending growth | +0.5% | +1.0% (inflation) |
| unexpected expenses per year | 0.83 | 0.30 |
| mean unexpected expense | CHF 950 | CHF 1,500 |
| annual bonus, share of salary | 1.1% | not modelled |

Reading: the engine sums a budget the way the ledgers do (a smoke check, not a validation),
and all the difference in our Swiss world comes from income tax: the UBS ledgers have **no
income tax line** and we charge Swiss income tax monthly on "net income".

**Decided (#48 item 1, PR for item 1): `profile.income_basis`.** Reading A (`net_before_tax`) is the
default and is what our tree uses; reading B (`take_home`, no income tax charged again) is the
basis of imported UBS synthetic profiles unless stated. With B, the Swiss-world replay of the
UBS profiles moves from −3.0 to +0.36 months of budget (what remains is inflation and wage
growth). The original question, for the record:

**What does UBS "net income" mean?** The kit does not define it
precisely. `docs/financial-concepts.md`: "Gross income is the amount before taxes and
deductions. Net income reflects relevant deductions". `docs/scenario-modelling.md` writes the
cash flow with a separate term "$T_t$ Taxes not already included in net income" and warns
"Do not deduct taxes twice". The starter kit "does not model … taxes".
- Reading A (ours today): net = after social contributions, before income tax, the Swiss
  payslip "Nettolohn"; residents pay income tax separately. Then charging tax is correct and
  the UBS ledgers simply omit it.
- Reading B: net = take-home after income tax. Then our engine taxes UBS profiles twice.
- Size of the effect: about 3 months of budget after 2 years for the median UBS profile
  (p10-p90: 1.2-4.5), i.e. roughly 12% of income. For our own tree the figures are ours, so
  reading A holds there; the question matters when UBS profiles are imported. Decide and
  label it (a `income_basis: "net_before_tax" | "after_tax"` field on the profile would make
  either reading explicit). The starter-kit reproduction (`core/starter.py`) switches tax off
  and matches exactly.

## 2. Components, methods and parameters

Monthly steps, 120 months, month index 0-based from `as_of`, CHF nominal; "real" = deflated by
the simulated CPI. The deterministic path is primary; Monte Carlo is an optional lens.

| # | component | method in code | parameters (default · verified?) |
|---|---|---|---|
| 1 | Wages / income | planned **net** income per month × wage index (CPI path + real wage growth); unemployment replaces it at a rate | `AS-real-wage-growth` 1%/yr ✓; tree income figures: the UBS kit ones ✓, 11 others unverified ✗ (raises, part-time pay, scholarship, internship, side income, later and Zurich salaries) |
| 2 | Income tax | one table of effective rates (8 points, single person, Lausanne, no church tax), linear interpolation on 12 × planned monthly income, × scale; paid in the same month | `AS-income-tax` table × 1.0 ✗ (third-party calculator, not ESTV) |
| 3 | Social contributions | **not modelled**: incomes are assumed net of AHV/IV/EO, ALV, BVG | — |
| 4 | Expenses / inflation | rent + other living costs, each × CPI path; one-off costs × CPI at their month | `AS-inflation-mean` 1%/yr ✓, `AS-inflation-sd` 0.8% ✓ (choice sized on FSO data) |
| 5 | Investments | one balanced portfolio; deterministic monthly factor (1+μ)^(1/12); MC lognormal with σ/√12; contributions only if cash allows; automatic sale to cover negative cash | `AS-investment-return` 4%/yr ✓ (Pictet, after a fee haircut), `AS-investment-vol` 10% ✗ |
| 6 | Cash interest | positive cash × monthly rate | `AS-cash-interest` 0.1% ✓ (Moneyland) |
| 7 | Debt | fixed-payment amortisation, monthly rate = annual/12, interest capitalised during deferral; `loan_change` changes payment/rate from a month | per-loan terms in nodes; study-loan rate ✗ |
| 8 | Unemployment | MC only: monthly hazard from an annual probability × weather multiplier; geometric spell; income × replacement rate | `AS-job-loss-prob` 3%/yr ✓ (SECO rate used as a proxy), `AS-unemployment-duration` 6 months ✗, `AS-unemployment-replacement` 70% ✓ |
| 9 | Unexpected expenses | MC only: Bernoulli per month, exponential size | `AS-unexpected-prob` 0.3/yr ✗, `AS-unexpected-mean` CHF 1,500 ✗ |
| 10 | Weather (named what-ifs) | deterministic overrides on the path: recession, inflation, market crash, job loss (catalog with start/duration/intensity) | catalog values ✗ (modelling choices) |
| 11 | Monte Carlo lens | 1,000 paths, seed 42, common random numbers across variants, independent shocks | — |
| 12 | Goals | liquid (cash + investments) or net worth at the end of the target month | profile goals (UBS synthetic) |
| 13 | Plan check | constraints: no funding gap (hard), debt service ≤ limit (hard), liquidity buffer (target), goals; feasibility first | `AS-liquidity-target` 3 months ✗, `AS-debt-service-limit` 33% ✗ (rules of thumb) |
| 14 | Exploration | levers (deterministic tornado), break-even vs siblings (crossover + income threshold), goal-seek (extra income), reverse stress (one-off cost), timing (12/24-month delay); k-ary threshold search assuming a monotone margin | search bound CHF 1,000,000 |
| 15 | Accounting checks | 8 identities on every run (cash flow, net-worth change, balance sheet, investment account, non-negativity, bands, sourcing) + `core.validation()` live checks | — |

Counts (from the files): 15 default assumptions (7 verified, 8 not), 24 tree assumptions (6 verified, 18 not).

## 3. Weaknesses a UBS judge could attack (ranked by how visible they are)

1. **Gross vs net is skipped.** Swiss payslips deduct AHV/IV/EO (employee 5.3%), ALV (1.1% up
   to the insured-salary cap), BVG (age-dependent credits on the coordinated salary) and
   accident insurance. We take "net income" as an input and never show this step, so a judge
   cannot see the pillar 1/2 effects of a decision (e.g. a master's delays BVG savings).
2. **One tax table for everything.** Single person in Lausanne applied to every node, including
   *Move abroad* (taxed with the Vaud table) and *Job in Zurich* (taxed as if in Vaud). No
   household types (couples and families are 49% of the UBS profiles), no deductions
   (professional expenses, insurance, 3a), the table is not from the official ESTV calculator,
   and tax is paid in the month the income arrives, while Swiss residents pay provisional
   instalments and settle a year later (a cash-timing effect that matters right after studies).
3. **No pillar 2 / 3a.** Retirement saving is the most "Swiss" part of personal finance and is
   absent: no BVG savings as a (non-liquid) asset, no 3a contribution lever with its tax
   deduction. A judge from UBS will likely ask "what about 3a?".
4. **Move abroad ignores currency and foreign rules.** Salary and costs are CHF at a constant
   rate; no EUR path, no FX shock, no foreign tax or social security, no health-insurance change.
5. **Unemployment rules are simplified.** The job-loss hazard uses the *stock* unemployment
   rate as an annual *inflow* probability (conceptually different); everyone with income is
   insured (students without 12 contribution months in 2 years are not; benefits stop after
   at most 520 daily allowances; insured salary is capped); no waiting days.
6. **Expenses move with one CPI.** Health-insurance premiums have historically grown faster
   than CPI; rents follow the reference mortgage rate and local markets; city cost differences
   only exist as node values. Couples' and families' shared costs are not modelled.
7. **Unsourced shock parameters.** Unexpected-expense frequency/size, unemployment duration,
   portfolio volatility, weather intensities are modelling choices without a source (labelled as
   such, but a judge will notice; the UBS generator itself uses ~0.8 surprises per year).
8. **Monte Carlo shocks are independent.** Recession, job loss and market returns do not
   co-move in the lens (they do in the named weather scenarios). Secondary, because the lens
   is off by default.
9. **Goals count borrowed cash.** A goal measured on "liquid" assets is met the month a loan is
   paid out (the card headline already uses net of debt; the goal check itself does not).
10. **Rules of thumb as constraints.** Liquidity target (3 months) and debt-service limit (33% of
    net income) are value judgements; the Swiss mortgage affordability rule is a different
    calculation (imputed rate + maintenance + amortisation against gross income).
11. **Exploration method limits.** Thresholds assume a monotone margin (otherwise `non_monotone`,
    no value); one lever at a time; reverse stress only as a month-0 cost; timing only delays the
    node's own decision; no search over combined decisions.
12. **Investments are simplified.** One portfolio, no explicit fees, no dividend/wealth tax,
    automatic liquidation without costs or tax, no rebalancing.

## 4. Ranked improvements

Score = impact on the rubric (C = modelling correctness 25, E = exploration 20, V = validation 15,
T = transparency 10) against effort (S < 1 h, M 1-3 h, L > 3 h). Ranked for tonight.

| rank | improvement | impact | effort | why first |
|---|---|---|---|---|
| 0 | ✅ Income basis made explicit (`income_basis`: net_before_tax / take_home), #48 item 1 | C+ T++ | S | done |
| 1 | ✅ Payroll layer: gross → net with AHV/IV/EO, ALV, NBU, BVG (#48 item 2) | C+++ T+ | M | done; see the design note for what changed |
| 2 | Tax by canton/household + abroad tax, ESTV-sourced points, optional arrears timing | C+++ | M-L | removes "Zurich/abroad taxed as Vaud" |
| 3 | Pillar 3a lever (+ tax deduction, locked asset) | C++ E++ | M | a new, very Swiss what-if per decision |
| 4 | Combined decisions + 2-lever surfaces + constraint-targeted search | E+++ | M | "what if master's AND share a flat", "what salary AND rent keep the plan feasible" |
| 5 | Currency for move abroad (EUR + EURCHF path + FX weather) | C++ E+ | M | the abroad branch becomes defensible |
| 6 | Unemployment eligibility, cap, 520 days, inflow hazard | C+ | S-M | cheap, fixes a known conceptual error |
| 7 | Category inflation (health premiums, rent reference rate) | C+ | S-M | small code, sourced parameters |
| 8 | Goals with a `net_of_debt` option, loan proceeds labelled | C+ T+ | S | removes a visible oddity |
| 9 | Property-based tests (random interventions keep every identity) | V++ | S | validation evidence for 15 points |
| 10 | Correlated MC regimes (recession ↔ job loss ↔ returns) | C+ | M | lens only, lower priority |
| 11 | Bonus / 13th salary in the income schedule | C+ | S | liquidity timing; UBS data has bonuses |
| 12 | Investment fees and taxes explicit | C+ T+ | S | transparency of the 4% figure |

### Designs

**1. Payroll layer (`core/payroll.py`).** Profile and node incomes may be given as `gross`
(new) or `net` (today; stays the default for compatibility). For gross: employee AHV/IV/EO rate,
ALV rate up to the insured-salary cap, BVG employee contribution = ½ × age credit rate ×
coordinated salary (gross − coordination deduction, clipped to the BVG band), accident insurance
rate. All rates are assumptions with sources (`targets.json` has the figures to verify). New
flows `social_contributions` and `bvg_savings`; BVG savings accumulate in a `pension` balance that
counts in net worth but not in liquidity (new identity: pension account moves only by credits and
interest). Tests: a gross salary in, the payslip identity out (net = gross − each line).

*Done (#48 item 2), with these differences from the design above:* the field is
`monthly_gross_income` (plus a `monthly_gross_income` intervention) rather than a gross/net flag,
so net profiles and the tree are untouched. The flows are `gross_income`, `social_contributions`
(AHV/IV/EO + ALV + NBU), `bvg_employee`, `bvg_employer`, informational only (`income` is already
net of them, so no cash identity changes). The BVG balance is returned in `payroll.bvg_balance`
but is **not** added to net worth yet: counting locked pension money in net worth changes the
headline and health of every gross node, so it is decided together with pillar 3a (item 4).
Rates 2026, verified: AHV/IV/EO 5.3%, ALV 1.1% to CHF 148,200, BVG entry 22,680 / coordination
26,460 / upper limit 90,720 / minimum coordinated 3,780, age credits 7/10/15/18%, minimum
interest 1.25%. Not verifiable as one figure (marked `verified: false` with a range): NBU (set by
each insurer, 1% [0.5–2%]) and the employee share of BVG credits (law: at most half; 0.5
[0.35–0.5]). Simplifications: thresholds are today's and move with the wage index (no separate
indexation), men's age bands, one employer, no BVG risk premiums or above-minimum plans.

**2. Tax.** `tax_tables` keyed by `(canton, household)` with points read from the ESTV
calculator (`SOURCES.md` lists them); profile `canton` and `household_type` (both in the UBS
data) select the table; a node can switch canton (Zurich) or country (abroad: a flat effective
rate assumption per country, labelled unverified). Taxable income = net − flat professional
deduction − insurance deduction − 3a. Optional `tax_timing: "arrears"`: year-t tax paid in
year t+1 in monthly instalments (a liability between), so graduating in a high-income year shows
the cash dip. Tests: the table reproduces the ESTV points; monotone in income; Zurich node uses ZH.

**3. Pillar 3a lever.** Intervention `pillar_3a` (monthly amount, capped at the annual maximum),
moved from cash to a locked `pension` balance with its own return; reduces taxable income in the
year. Exploration gains "3a vs invest vs cash" as levers and a goal-seek on the contribution.

**4. Richer exploration.** (a) `combine(node_a, node_b)` = interventions of both paths (the
engine already accepts custom nodes on any parent), with conflict rules (later wins, listed);
(b) 2-lever surface: a small grid of two assumptions → feasibility map (plan_check level per
cell) and the break-even contour; (c) constraint-targeted search: smallest income / largest rent
such that `plan_check.level` holds (reuse the k-ary search with a 0/1 margin); (d) timing scan:
plan check and final net worth for start months 0..36, the latest start that still holds.

**5. Currency.** Node-level `currency: "EUR"` on income/expense interventions + assumption
`EURCHF` path (constant by default, a weather `chf_strengthens` / `chf_weakens` as a shift);
amounts converted each month; FX shown in `flows`. Tests: constant rate reproduces today exactly.

**6. Unemployment.** Eligibility flag from the income history (≥ 12 of the last 24 months with
income), benefit cap at the insured-salary maximum, duration cap (520 daily allowances ≈ 24
months, shorter for under-25s without children — to verify), hazard = annual inflow into
unemployment (SECO entries / labour force) instead of the stock rate.

**7. Category inflation.** Split `other_expenses` into health insurance and the rest; health
premium growth and rent indexation (reference rate) as their own assumptions.

## 5. What to tune tonight, and what not

Tunable against public sources with `core.bench.search` / `score` (fill `targets.json` first;
`core/bench/params.json` tags every parameter `tunable` or `rule`, `search` refuses rules, and
`python -m core.bench --params FILE` scores a candidate set):
inflation mean, real wage growth, balanced return and volatility, unemployment duration,
unexpected-expense frequency/size, the tax table points. **Not tunable** (they are rules or
value judgements, to be sourced or labelled, never optimised): contribution rates, thresholds,
liquidity target, debt-service limit, weather intensities, health-score weights. Do not tune any
parameter to the UBS ledgers: they are synthetic and have no tax line (see section 1).

Note: the `unemployment-rate` target has weight 0, because the stock rate it holds is not the
hazard the engine needs (weakness 5); tuning against it would reward the known error.

Suggested order for the session: (0) decide the "net income" reading above; (1) verify the `to_verify` / `to_fill` targets and figures in
`SOURCES.md`, re-run `python -m core.bench`; (2) build improvement 1 (payroll) and the tax table
from ESTV points (2, Vaud + Zurich only first); (3) improvement 4 (combined decisions, 2-lever
surface) for the exploration score; (4) improvement 9 (property tests) as validation evidence.
