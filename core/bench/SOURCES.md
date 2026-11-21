# Public Swiss sources to verify the engine's figures (#42)

For each figure: where it is used, the public source, and exactly what to read there. Figures
marked "known, to verify" are what we believe the source says; nobody has checked them against
the primary page yet. After checking, update the assumption (`verified: true`, `retrieved`, exact
`source`) and the matching entry in `core/bench/targets.json` (`status: "verified"`), then run
`python -m core.bench`.

## A. Default assumptions (`core/data/assumptions_ch.json`) not yet verified

| assumption | value now | source | what to check |
|---|---|---|---|
| `AS-income-tax` (table) | effective rate 1% at 15k … 27% at 250k | ESTV tax calculator https://swisstaxcalculator.estv.admin.ch | single, no church, Lausanne (VD), effective federal + cantonal + communal rate at taxable income 15k, 30k, 50k, 70k, 100k, 150k, 250k; repeat for Zurich (ZH) and married couple for the tax-by-canton improvement |
| `AS-investment-vol` | 10%/yr | Pictet BVG/LPP index series https://www.group.pictet/asset-management/indices (or a balanced fund factsheet) | annualised volatility of a 25-40% equity Swiss pension-fund style index over 10-20 years |
| `AS-unemployment-duration` | 6 months | SECO labour market statistics https://www.amstat.ch | average duration of registered unemployment (months), latest year |
| `AS-unexpected-prob`, `AS-unexpected-mean` | 0.3/yr, CHF 1,500 | FSO Household Budget Survey (HABE/EBM) https://www.bfs.admin.ch/bfs/en/home/statistics/economic-social-situation-population/income-consumption-wealth/household-budget.html | irregular spending categories (repairs, health out-of-pocket) per household per year; otherwise keep as labelled modelling choices |
| `AS-liquidity-target` | 3 months | (value judgement) | keep labelled; optionally cite a consumer-advice source (e.g. Swiss budget counselling, Budgetberatung Schweiz https://www.budgetberatung.ch) |
| `AS-debt-service-limit` | 33% | FINMA-recognised SBA guidelines on mortgage affordability https://www.swissbanking.ch | note that the Swiss rule uses an imputed interest rate + maintenance + amortisation against GROSS income; keep ours labelled as a different, simpler rule |
| `AS-job-loss-prob` (method; its target in `targets.json` has weight 0 until fixed) | stock rate 3% used as hazard | SECO / FSO labour force (SAKE/ESPA) inflows https://www.bfs.admin.ch | annual inflow into unemployment as a share of the labour force (the correct hazard) |

## B. Tree assumptions (`core/data/trees/alexia.json`) with `verified: false`

| assumption | value now | source | what to check |
|---|---|---|---|
| `AS-alexia-work-rent` | CHF 1,100/month | FSO rent statistics by canton https://www.bfs.admin.ch/bfs/en/home/statistics/construction-housing/dwellings/rented-dwellings.html | average rent of a 1-room / 1.5-room flat in Lausanne or Vaud |
| `AS-alexia-zurich-rent` | CHF 1,500/month | same FSO table | 1-room flat, city of Zurich |
| `AS-alexia-abroad-rent` | CHF 1,200/month | Destatis / Eurostat rent statistics (e.g. Berlin) https://www.destatis.de | 1-room flat in the chosen city, converted at a stated EURCHF |
| `AS-alexia-raise`, `AS-alexia-promotion`, `AS-alexia-abroad-promotion` | 5% / 15% / 15% | FSO Swiss Earnings Structure Survey (LSE/ESS) https://www.bfs.admin.ch/bfs/en/home/statistics/work-income/wages-income-employment-labour-costs.html | median salary growth between age bands 20-29 and 30-39 for graduates; typical promotion step if published |
| `AS-alexia-zurich-salary` | CHF 5,400/month net | FSO LSE by region (Zurich) | median net salary, 25-30, tertiary education, Zurich region |
| `AS-alexia-later-master-salary` | CHF 5,200/month net | FSO graduate survey https://www.bfs.admin.ch (Hochschulabsolventenbefragung) | median salary one/five years after a master's |
| `AS-alexia-parttime-income`, `AS-alexia-80pct-income` | 60% / 80% of CHF 4,200 | same LSE (part-time pay is roughly proportional) | confirm proportionality; student jobs may pay less |
| `AS-alexia-side-job`, `AS-alexia-side-project` | CHF 600 / 400 per month | (illustrative) | keep labelled unless a student-job wage survey is cited |
| `AS-alexia-scholarship` | CHF 500/month | Vaud grants (Office cantonal des bourses d'études) https://www.vd.ch ; EPFL social scholarship https://www.epfl.ch/education/studies/en/epfl-social-scholarship/ | typical monthly grant for a master's student living alone |
| `AS-alexia-internship` | CHF 2,500/month | EPFL internship guidelines https://www.epfl.ch | recommended minimum monthly pay for a master's internship |
| `AS-alexia-study-loan-rate` | 2% | Vaud study loans https://www.vd.ch | interest rate of cantonal study loans (often interest-free during studies) |
| `AS-alexia-equity-return`, `AS-alexia-equity-vol` | 5.5% / 15% | Pictet 1926-2024 study https://www.group.pictet/asset-management/performance-swiss-shares-bonds | 80/20 mix of the published share and bond returns, minus fees |
| `AS-alexia-car-resale` | CHF 7,000 after 2 years | Eurotax / TCS used-car depreciation https://www.tcs.ch | depreciation after 2 years of a CHF 15,000 car |

## C. Swiss rules the engine does not model yet (needed for the improvements)

Known figures, to verify on the primary page before use:

| rule | known figure (to verify) | source |
|---|---|---|
| AHV/IV/EO employee contribution (check the 2026 rates) | 5.3% of gross salary (AHV 4.35% + IV 0.7% + EO 0.25%) | https://www.ahv-iv.ch/en/Social-insurances/Contributions |
| ALV employee contribution | 1.1% up to the insured-salary cap CHF 148,200/year | https://www.arbeit.swiss |
| BVG entry threshold / coordination deduction (2025; check the 2026 value) | CHF 22,680 / CHF 26,460 per year | https://www.bsv.admin.ch |
| BVG age credits (total, split employer/employee at least half each) | 7% (25-34), 10% (35-44), 15% (45-54), 18% (55-65) | https://www.bsv.admin.ch |
| Pillar 3a maximum with a pension fund (2025; check the 2026 value) | CHF 7,258 per year | https://www.estv.admin.ch |
| Unemployment insurance duration | up to 520 daily allowances depending on age and contribution period; 12 contribution months in the last 2 years required | https://www.arbeit.swiss |
| Health insurance premium growth | FOPH annual premium change for the basic insurance (KVG/LAMal) | https://www.bag.admin.ch |
| Reference mortgage rate for rents | current rate and the rent adjustment rule (e.g. ±3% rent per 0.25 pt) | https://www.bwo.admin.ch |
| EURCHF | SNB monthly exchange rates | https://data.snb.ch |

## D. Already verified (for reference)

FSO CPI 2023-2025, FSO wage index 2024-2025, Pictet share/bond returns, Moneyland savings rate,
SECO unemployment rate, unemployment insurance replacement 70%/80%, EPFL tuition CHF 780/semester,
UBS starter-kit figures (salaries, tuition, move cost).
