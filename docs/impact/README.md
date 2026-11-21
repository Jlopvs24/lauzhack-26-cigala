# IMC Tech for Good: understanding an exchange budget before committing

Prepared for [issue #16](https://github.com/Jlopvs24/lauzhack-26-cigala/issues/16). Sources checked on **21 November 2026**. This is an impact case and a proposed pilot, not a report of achieved impact or an agreement with a partner.

## The problem and the evidence

A grant amount does not tell a student whether they can finish an exchange without running out of cash. Rent, the payment date of the grant, available savings and a reserve for the return journey all matter. Students need a way to inspect those trade-offs before signing a lease or booking travel.

| Observation | Primary source and scope | What it supports |
| --- | --- | --- |
| 18% of assessed students lacked basic financial-literacy proficiency, on average across the 14 participating OECD countries. | [OECD, PISA 2022 Results, Volume IV (2024)](https://www.oecd.org/en/publications/pisa-2022-results-volume-iv_5a849c2a-en.html). The assessment concerns **15-year-olds**, not university or Erasmus students. | A need for accessible financial education; it does not estimate financial literacy among exchange students. |
| 35.63% reported insufficient funding for living costs; 62.7% received their grant after departure. | [ESN, XV ESNsurvey, key findings published 21 November 2024](https://esnsurvey.org/). These are survey responses, not a representative census of all students. | Both the size and timing of support deserve attention. |
| The published Zurich exchange-student budget is CHF 1,850/month, including CHF 800 rent. | [University of Zurich, Finances and Scholarships](https://www.int.uzh.ch/en/in/finances.html). Its rent reference comes from the shared ETH/UZH Housing Office; individual costs vary. | A local reference budget for the fictional Zurich case below, not a guaranteed housing offer. |
| ETH lists CHF 2,200 per semester for SEMP students from Spanish home universities, covering five months and paid at the beginning of the semester. | [ETH Zurich, SEMP fact sheet, Scholarships](https://ethz.ch/en/studies/non-degree-courses/exchange/downloads/for-partners/factsheets/semp.html). Eligibility requires an exchange place; the student's award letter remains the source for their actual grant. | A grant is a contribution towards costs, not a complete semester budget. |

Our hypothesis is that an understandable, inspectable budget helps students recognise a funding gap and ask for support earlier. We prioritise first-generation and exchange students who lack someone to review their plan. The sources above do **not** measure how many students cannot afford a financial adviser, and we should not pitch that claim as an established statistic.

The tool cannot create affordable rooms or increase grants. Its contribution is financial understanding and earlier referral, with the decision left to the student.

## A concrete non-profit deployment

[Erasmus Student Network describes itself as a non-profit international student organisation](https://esn-spain.org/que-es-esn). An ESN section, working with its university's international office, is a plausible pilot host. **ESN has not been contacted and no partnership is agreed.**

Proposed use: during a pre-departure session, before the student commits to accommodation, a volunteer spends ten minutes with them entering savings, dated funding and an actual rent offer. The student compares three scenarios, checks the assumptions and explains the funding gap back to the volunteer. Someone with an unresolved gap gets a referral to the international office or a recognised student-support service. This replaces a repeated first budget walkthrough assembled from scattered grant and housing pages; it supplements the office's eligibility checks and individual advice.

The university could host the existing web app and Python API on a managed machine for the session. Remote access, HTTPS for microphone use, operation and maintenance would need an agreed host; production hosting is not part of this issue. Manual input and engine calculations provide the core activity without a paid model. Voice and document extraction are optional and depend on the configured services. Use synthetic documents for the first pilot and collect anonymous evaluation scores separately; do not promise that browser speech services or cloud extraction keep personal data on the device.

Students pay nothing in the proposed pilot. The host still supplies a machine, connectivity and staff time: **one hour of preparation plus 30 ten-minute sessions = six staff-hours** is a planning assumption, not a measurement. The [synthetic extraction benchmark](../../multimodal/benchmark/RESULTS.md) reports a rounded mean of USD 0.00019/document; 90 comparable documents would be about USD 0.02 for extraction alone. That excludes chat, speech transcription, retries, hosting and labour, and is not a real-document cost guarantee. Record actual API spend and volunteer time; an initial **USD 5 paid-API cap** is a proposed pilot budget. The volunteer would stop paid calls at the cap and use manual input; automatic enforcement is not implemented.

## Fictional persona: Nora, a semester in Zurich

Nora is a 21-year-old Spanish first-generation university student with an assumed nominated exchange place at ETH Zurich. She is fictional, not a survey respondent. She has **CHF 6,500 of spendable savings after setting aside travel, arrival charges and any blocked rental deposit**. Those reserved funds are outside this five-month model, are not counted as investments and must not be read as accessible emergency cash. No wage income, loan or family contribution is assumed.

| Input | Basis |
| --- | --- |
| Five-month window, September 2026 to January 2027; CHF 2,200 grant at month 0 | Semester illustration using the ETH SEMP terms cited above. Confirm the actual amount and payment date before use. Model the grant as a one-off cash receipt, not salary subject to the engine's wage-growth/job-loss logic. |
| CHF 800 rent and CHF 1,050 other expenses per month | UZH's reference budget: meals 450, insurance 200, transport 100, miscellaneous 250 and study materials 50. This is a city benchmark, not an ETH quote or an individual insurance assessment. |
| CHF 6,500 spendable savings; CHF 500 return reserve | Fictional personal inputs and a chosen reserve target, not a population average or a recommended minimum. |
| A CHF 600 room, or CHF 1,500 additional support | Hypothetical alternatives. The room requires a confirmed offer; the support requires approval and receipt. Neither is a promised price or published award amount. |

The three choices are: **accept the reference room**, **accept a confirmed lower-rent room**, or **wait for additional funding before accepting the reference room**. The third branch is conditional: without approval and receipt, its result does not apply. [ETH lists the Heyning-Roelli Foundation as one possible support route](https://ethz.ch/en/studies/non-degree-courses/exchange/preparation.html); awards are selective, and housing supply is limited. A referral is not a funding commitment.

### Engine-compatible inputs

Each decision is a standalone custom node accepted by `core.simulate`, or by `POST /simulate` with `{profile, node, assumptions, weather}`. No Alexia interventions are inherited. This is a documented scenario fixture; it is **not wired into the app's Alexia tree**. Money is in CHF throughout, without an assumed EUR/CHF conversion.

```json
{
  "profile": {
    "profile_id": "IMC-EXCHANGE-01",
    "display_name": "Nora (fictional)",
    "age": 21,
    "city": "Zurich",
    "currency": "CHF",
    "as_of": "2026-09-01",
    "horizon_months": 5,
    "employment_status": "student",
    "cash": 6500,
    "monthly_net_income": 0,
    "monthly_rent": 800,
    "monthly_other_expenses": 1050,
    "monthly_investment_contribution": 0,
    "assets": [],
    "liabilities": [],
    "goals": [{"name": "Return reserve", "target": 500, "target_date": "2027-01-31", "priority": "high", "metric": "liquid"}]
  },
  "assumptions": [],
  "weather": [],
  "decisions": [
    {
      "node_id": "imc-standard",
      "label": "Accept the reference room",
      "interventions": [
        {"param": "one_off_income", "month": 0, "value": 2200, "label": "SEMP grant received at semester start"}
      ]
    },
    {
      "node_id": "imc-shared",
      "label": "Accept a confirmed lower-rent room",
      "interventions": [
        {"param": "one_off_income", "month": 0, "value": 2200, "label": "SEMP grant received at semester start"},
        {"param": "monthly_rent", "op": "set", "value": 600, "from_month": 0, "to_month": 5, "label": "Confirmed lower-rent room"}
      ]
    },
    {
      "node_id": "imc-funded",
      "label": "Wait for additional funding before committing",
      "interventions": [
        {"param": "one_off_income", "month": 0, "value": 2200, "label": "SEMP grant received at semester start"},
        {"param": "one_off_income", "month": 0, "value": 1500, "label": "Additional support only if approved and received"}
      ]
    }
  ]
}
```

### Results calculated by the existing engine

Calculated with `core-1.0`, seed 42, 1,000 paths, default Swiss assumptions, no weather, and sensitivity disabled. The deterministic result includes the engine's inflation and cash interest; it is not simply five times the initial budget. September is month 1 in the display, index 0 in the API.

| Choice | Deterministic cash at end of January (CHF) | First negative month | Simulated paths with a cash shortfall |
| --- | ---: | --- | ---: |
| Reference room | -563.46 | January, month 5 (`4` in the API) | 100.0% |
| Confirmed lower-rent room | 438.37 | None | 9.2% |
| Additional funding received, reference room | 937.04 | None | 6.2% |

The reference plan has an unfunded gap; negative cash is **not an automatic loan**. The lower-rent choice avoids a deterministic shortfall but still misses Nora's chosen CHF 500 reserve. Even the funded branch has adverse simulated paths. These percentages are conditional on illustrative engine assumptions, including unexpected expenses; they are **not measured real-world probabilities or evidence of pilot impact**. The default tax model is for Lausanne, so this no-wage case does not establish a Zurich employment/tax model.

For a delayed-payment check, change the grant's `month` to `2` in every branch and rerun; keep the amount unchanged. An award and its receipt date are different assumptions. This is a stress scenario, not a claim that ETH normally pays late. If a room or extra funding is unconfirmed, retain the reference branch and refer the student to the office rather than showing a conditional branch as affordable.

### Reproduce and check

From the repository root, with the engine dependencies installed (`numpy`), run this Python snippet. It reads the JSON above, checks the three documented amounts and the month convention, and verifies every accounting check returned by the engine. It makes no paid API calls.

```python
import json
from pathlib import Path
import core

text = Path("docs/impact/README.md").read_text(encoding="utf-8")
case = json.loads(text.split("```json\n", 1)[1].split("```", 1)[0])
expected = {"imc-standard": -563.46, "imc-shared": 438.37, "imc-funded": 937.04}
assert len(case["decisions"]) == 3
for node in case["decisions"]:
    result = core.simulate(case["profile"], node, case["assumptions"],
                           case["weather"], n_paths=1000, seed=42, sensitivity=False)
    assert result["checks"] and all(c["passed"] for c in result["checks"])
    assert len(result["deterministic"]["cash"]) == 6
    assert result["metrics"]["final_cash"] == expected[node["node_id"]]
    expected_month = 4 if node["node_id"] == "imc-standard" else None
    assert result["metrics"]["first_negative_month"] == expected_month
    print(node["node_id"], result["metrics"]["final_cash"], result["trace_id"])
```

## Pilot metric: can students explain the gap?

Propose **30 consenting students** at one section's pre-departure session. Before and after the ten-minute activity, give equivalent, differently numbered budget exercises with engine-verified answers; alternate their order. A reviewer scores whether the student correctly identifies (1) the funding gap, (2) the first negative-cash month or that there is none, and (3) one assumption that still needs confirmation. All three are required to pass.

The primary metric is **post-session pass rate minus pre-session pass rate**, in percentage points. For each rate, the numerator is the number passing and the denominator is all 30 enrolled participants; missing responses count as not passing and are reported separately. **A 20-percentage-point gain is a proposed success target, not a result.** Report counts alongside rates, volunteer minutes and actual API cost. The small pilot tests comprehension and feasibility; it cannot establish reduced debt, increased mobility participation or causality without a comparison group and longer follow-up. No pilot has been run.

## IMC pitch draft: 30-40 seconds

> A grant is not a budget. ESN's survey found that more than a third of students reported insufficient funding for living costs. Our financial twin lets a student compare rent and funding choices, see when cash runs out, and inspect every assumption. The engine calculates; Lumi explains. An ESN volunteer could offer this free before a student signs a lease, then refer unresolved gaps to the university. Our proposed pilot asks whether thirty students can identify their funding gap more accurately after ten minutes. We have a working simulator; the partnership and impact still need testing.

96 words: approximately 36-40 seconds at 145-160 words per minute. Rehearse with the speaker. The student scenario above is an offline reproducible example; the existing app demo uses Alexia.
