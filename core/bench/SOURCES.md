# Public Swiss sources to verify the engine's figures (#42)

For each figure: where it is used, the public source, and exactly what to read there. Figures
marked "known, to verify" are what we believe the source says and still need a check against
the primary page (section C). After checking, update the assumption (`verified: true`, `retrieved`, exact
`source`) and the matching entry in `core/bench/targets.json` (`status: "verified"`), then run
`python -m core.bench`.

## A. Verification pass of 21 Nov 2026 (#48 item 7)

Every assumption that was `verified: false` was checked against a primary source. Status:
**verified** = the cited figure was read on the source and the assumption now carries its URL;
**corrected** = verified and the value changed; **labelled** = no authoritative figure exists, the
value stays a modelling choice (`verified: false`) with the reason in its `source`.
The exact URLs are in each assumption's `source` field.

### Defaults (`core/data/assumptions_ch.json`)

| assumption | before → after | source | status |
|---|---|---|---|
| `AS-investment-vol` | 10% → 10%, range 5-12% | Pictet 1926-2024, Table 1: SD 19.9% shares, 3.9% bonds, correlation 28% → 50/50 mix 10.7%. Pictet LPP-25/40 fund factsheets: 4.5% / 5.5% | verified (derived) |
| `AS-unemployment-duration` | 6 → 5.8 months | SECO "Die Lage auf dem Arbeitsmarkt" Dec 2024, table 5: mean 5.8 (median 4.0; 3.2 for ages 15-24). Elapsed duration of current spells | corrected |
| `AS-job-loss-prob` | 3% → 3% (source text only) | Same SECO report, table 7: 12,627 registrations from employment in the month → about 3.5% a year of the employed (one seasonally high month) | verified already; hazard cross-check added |
| `AS-3a-return` | 1% → 0.21% | Moneyland 3a analysis, Oct 2026: unweighted average of 93 providers | corrected |
| `AS-bvg-employee-share` | 0.5 → 0.5 | BSV / Art. 66 BVG: employer pays at least half. Swisscanto 2025: market average about 0.42 (kept in the range, not used: those plans also save more than the minimum the model computes) | labelled (legal bound checked) |
| `AS-nbu-rate` | 1% → 1%, range 0.4-2% | No single official rate (insurer and risk class). Suva: total premiums 1.9% of wages; ESTV calculator default 0.4% | labelled |
| `AS-tax-abroad-rate` | 15% → 15% | OECD Taxing Wages 2025: income tax + employee contributions at the average wage 22.5% (ES) to 37.4% (DE). Income-tax-only rows at 67% of the average wage not readable | labelled |
| `AS-unexpected-prob`, `AS-unexpected-mean` | 0.3/yr, CHF 1,500 → same | FSO Household Budget Survey has no line for irregular one-off spending | labelled |
| `AS-liquidity-target` | 3 months → same | Consumer advice (Beobachter): three months of expenses; no official figure | labelled (value judgement) |
| `AS-debt-service-limit` | 33% → same | FINMA Supervisory Notice 02/2025: 33% of sustainable GROSS income, imputed 5% interest, 0.8% running costs (mortgages). Ours is a simpler rule on net income | labelled (value judgement) |
| `AS-auto-liquidate` | flag → same | engine rule | labelled (rule) |

### Tree (`core/data/trees/alexia.json`)

| assumption | before → after | source | status |
|---|---|---|---|
| `AS-alexia-work-rent` | CHF 1,100 → 1,100, range 900-1,300 | Statistique Vaud Numerus 8-2026: Vaud 1 room CHF 896, 2 rooms CHF 1,198; Lausanne CHF 20.3/m² vs 19.1 | verified |
| `AS-alexia-zurich-rent` | CHF 1,500 → 1,500 | Statistik Stadt Zürich, Mietpreise 2026: 2-room flat CHF 1,497 | verified |
| `AS-alexia-zurich-salary` | CHF 5,400 → 5,150 | FSO wage survey 2024: Zurich region CHF 7,502 vs Lake Geneva 6,998 (+7.2%), applied to the starter-kit CHF 4,800 | corrected (ratio verified, base illustrative) |
| `AS-alexia-study-loan-rate` | 2% → 0% | vd.ch: Vaud study loans are interest-free during the studies and 5 years after; then 5% late interest | corrected |
| `AS-alexia-scholarship` | CHF 500 → 744, range 0-2,100 | FSO student survey 2024: median study aid CHF 597/month, CHF 744 away from parents. EPFL social scholarship: at most CHF 2,100 | corrected |
| `AS-alexia-internship` | CHF 2,500 → 2,000, range 2,000-3,500 | EPFL: recommended minimum CHF 2,000/month | corrected |
| `AS-alexia-equity-return` | 5.5% → 5.5% | Pictet Table 1: 7.7% shares, 4.0% bonds (geometric) → 80/20 mix 6.9% before costs; the 1.4-point deduction is ours | verified (derived) |
| `AS-alexia-equity-vol` | 15% → 16% | Pictet Table 1 → 80/20 mix 16.2% | corrected |
| `AS-alexia-parttime-income`, `AS-alexia-80pct-income` | 60% / 80% of CHF 4,200 → same | FSO wage survey (via Statistique Vaud Numerus 6-2026): pay is proportional above a 50% workload | verified |
| `AS-alexia-car-resale` | CHF 7,000 → 10,000, range 7,000-12,000 | TCS cost-per-km method: about 20% loss after 2 years (booklet not opened); market sources about 35% | corrected, still labelled |
| `AS-alexia-abroad-rent` | EUR 1,301 (CHF 1,200) → same | Berlin Mietspiegel 2026 (EUR 7.71/m²) covers existing leases only; no official new-lease figure | labelled |
| `AS-alexia-raise`, `AS-alexia-promotion`, `AS-alexia-abroad-promotion` | 5% / 15% / 15% → same | FSO publishes wage by age band (+25% from 20-29 to 30-39) but no size of a single raise or promotion | labelled |
| `AS-alexia-later-master-salary` | CHF 5,200 → same | Starter-kit scale + experience; see the note below | labelled |
| `AS-alexia-side-job`, `AS-alexia-side-project` | CHF 600 / 400 → same | FSO student survey: 72% of students work; income from work only in annex tables | labelled |

**Finding to decide (not changed here):** the starter-kit salaries are below Swiss graduate
medians. FSO graduate survey 2023: CHF 80,900 gross a year one year after a university master's
(about CHF 5,850 net a month) against the kit's CHF 4,800; CHF 80,300 after a UAS bachelor against
CHF 4,200 for "start working" (which fits a 20-year-old without a degree: Vaud median under 25 is
CHF 5,040 gross, about 4,385 net). The kit figures are kept because the demo reproduces the UBS
starter kit; they are overridable assumptions with these medians inside or next to their ranges.

Other figures read during the pass, not used by the model yet: Vaud health premium 2026 CHF 527.10
(adults) / 371.00 (19-25) a month (FOPH); EPFL student budget CHF 1,310 a month without rent;
EURCHF 0.928 (SNB, Oct 2026 monthly average; the model uses the ECB rate of 20 Nov, `AS-eurchf`).

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
