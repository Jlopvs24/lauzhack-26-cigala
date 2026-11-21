# Pitch and demo script

One story, Alexia, told in under three minutes, hitting UBS (main), AXA and IMC. The climax is **Make it mine**: Alexia adds her own condition and the branch re-grows. Booth variants and a Q&A cheat sheet follow.

> **Never type an engine figure by hand.** Every number below comes from `python scripts/pitch_figures.py` (engine `core-1.1`, Alexia's demo profile, default assumptions, Sat 21 Nov 20:50). The engine is still changing tonight. **Re-run the script before rehearsing and before submitting**, and update every number in this file, the README and `docs/submission/` that changed. Lumi's lines are produced by `web/src/scene/narration.js` from engine fields, not by an LLM. The script prints them too.

## Before you start (3 minutes)

- Chrome or Edge, full screen, at `http://127.0.0.1:5175`. Language **EN**. Sound **on**: the first click unlocks audio.
- The API is running on port 8000. `/health` shows `"engine": "core"`, `"personal_conditions_supported": true` and Kokoro `available: true`.
- The header shows the **Verified 6/6** badge.
- **Make it mine** appears on the current branch (the component is `web/src/personalize/MakeItMine.jsx`). On Sat 20:50 it was not yet mounted in `web/src/main.jsx` on `master`. If it is still missing, the climax can't be shown in the app: use the standalone page `web/src/personalize/demo.html` and say so.
- Clear the session's conditions before you start: **Your conditions** → remove all, or open a new private window. Conditions persist per browser session.
- Optional AXA beat: the three demo documents are on the desktop (`data/synthetic/docs/P00001-payslip.jpg`, `P00001-bank_statement.pdf`, `P00001-rental_contract.jpg`). **Do this beat only if extraction takes 10 s or less on the demo laptop.** On the shared API on Sat 20:40 it took 57–74 s per photo.
- Rehearse at least twice against a timer.

## Main demo: 2:50

| Time | Screen and clicks | Say | Lumi says (aloud) |
|---|---|---|---|
| **0:00–0:15** Hook (IMC) | Start portal: *"Every choice grows a different tree."* | "This is Alexia. She's 20, studies in Lausanne and has CHF 8,000 saved. Should she start working, do a master's or move abroad? She can't afford a financial adviser, and a chatbot would make up numbers. So we built her a financial twin she can explore, and make her own." | – |
| **0:15–0:30** Roots (AXA) | **Try the demo: Alexia**. The camera rises from the roots to the tree. (Optional, if extraction is fast: **Start with your own roots** → **Add documents** → the three `P00001-*` files → **Read my roots** → point at *Source · extraction confidence* → **Grow my tree**.) | "Her roots can come from a payslip photo, a bank statement and a lease. This laptop reads them with local OCR and a small model, and calls a vision model only if a check fails: 97.7% accuracy at 1/154th of the frontier model's cost." | (root line, may be cut by the next click) |
| **0:30–0:55** The hook (UBS) | Click the **Do a master's** limb; the camera flies in. Point at its card: plan check and *what it trades*. | (Stay quiet while Lumi speaks, then:) "That's the UBS starter kit's own result: the master's runs out of cash in month 7. We reproduce the kit exactly, and then make it Swiss: payroll deductions, the official 2026 income tax for her city, pillar 3a." | *"Do a master's. Two years of master's with a student job, then a better-paid job. Plan check: needs financing. In this scenario the cash runs short from month 7. From here: student job only, study loan of CHF 15,000 or part-time master's with a 60% job. The other branches stay in grey so you can compare."* |
| **0:55–1:20** What would have to be true (UBS) | **Report** (header) → *What would have to be true*. | "We don't predict; we ask what would have to be true. Her salary after the master's matters most. Against starting work, the break-even is CHF 4,960 a month, and starting a year later costs 17,628. But no salary fixes month 7: that's a cash problem, not a wealth problem." | – (Lumi stays quiet over reports) |
| **1:20–2:05** **Make it mine (climax)** | **Esc**. On *Do a master's*: **Make it mine** → **Speak** (or type) *"I'd get a CHF 600 a month scholarship during the master's"* → **Check it** → *Here is how I understood it*: **+CHF 600/month income, months 1–24**, *"Every number here comes from what you said; nothing is invented."* → **Apply to this branch** → **Confirm**. The branch re-grows. | "But Alexia knows something the model doesn't: she'd get a scholarship. She just says it. A small model turns her words into one change, and only with numbers she said. She confirms, and the engine re-grows this branch and everything under it. The gap shrinks from CHF 18,553 in month 7 to 3,914 in month 13. And look at the study loan: it needed financing a minute ago, and now it holds, in all four stress scenarios. Or she can add it as a new branch and compare it with the original." | – |
| **2:05–2:30** Her path report (UBS) | Click **Study loan of CHF 15,000** → **Repay over about 5 years** → **Open your report**. Scroll: the brief, *her conditions*, the stress scenarios (holds in every row) and *Validation and reproducibility*. Click the **Verified 6/6** badge. | "Her report, with her own condition in it, ready to save as a PDF. Every number has a trace id. Six checks run live on the engine: accounting identities on all 40 nodes, reproducibility, monotonicity, isolation, the UBS kit, and re-verified thresholds. Six out of six." | *"Study loan of CHF 15,000. … Plan check: holds. In this scenario the cash never runs out. …"* (on the way) |
| **2:30–2:50** Close (IMC) | Back on the tree. Optional: switch to **ES**, and Lumi re-reads the node in Spanish with a Spanish voice. | "Lumi explains and never recommends. Cigala is free, works in four languages and listens to your own words. A student-network volunteer could run it in ten minutes, before a student signs a lease. Explore, don't predict, and make it yours. Thank you." | – |

**If something breaks:**

- **The proposal asks a question instead** (for example *"For how many months?"*): answer *"for the two years of the master's"*. That also shows it never guesses.
- **Make it mine returns a question with no proposal** (the LLM is unreachable or the daily budget is spent): play shot 5 of the backup video. Before judging, check `/health` → `llm_budget.remaining_usd`.
- **Extraction is slow:** skip it (see *Before you start*). Say the AXA line over the tree.
- **No audio:** read Lumi's bubble aloud yourself, or use **Sound off**; the bubble text is identical.
- **Leftover conditions from a rehearsal** change every number: remove them under **Your conditions**, or use a new private window.

## Booth variants (30–40 s each)

### UBS booth

> You told us Monte Carlo predicts and you want to explore. So our engine is deterministic, and it reproduces your starter kit's three scenarios to the franc. Then we made it Swiss: payroll deductions, official 2026 income tax for twelve cities and three household types, and pillar 3a. On each branch it asks what would have to be true: break-even salary, the smallest shock that breaks the plan, the cost of waiting a year. And the twin becomes yours: say "I'd get a CHF 600 scholarship", confirm, and that branch re-grows. A funding gap is never hidden behind a score. Six checks run live.

(104 words, about 40 s)

**Show:** the master's card → Report → *What would have to be true* → **Make it mine** with the scholarship → **Verified 6/6**.

### AXA booth

> We use the smallest model that works at every step. A payslip photo is read by local OCR and a small model with an 800-token budget. Deterministic checks follow, and only if one fails does that document go to a cheap vision model. On 60 synthetic Swiss documents that is 97.7% field accuracy against 99.4% for the frontier model, at 154 times lower cost. "Make it mine" turns a spoken sentence into one engine change for a hundredth of a cent. Lumi's voice is local Kokoro, at zero cost. The session's API cost is shown, and a daily budget guard falls back to templates.

(104 words, about 40 s)

**Show:** the benchmark table in [`multimodal/benchmark/RESULTS.md`](../multimodal/benchmark/RESULTS.md); *Session API cost* in the chat panel; the roots review with source and confidence per field.

### IMC booth

Lluc's sourced 96-word draft from [`docs/impact/README.md`](impact/README.md), unchanged:

> A grant is not a budget. ESN's survey found that more than a third of students reported insufficient funding for living costs. Our financial twin lets a student compare rent and funding choices, see when cash runs out, and inspect every assumption. The engine calculates; Lumi explains. An ESN volunteer could offer this free before a student signs a lease, then refer unresolved gaps to the university. Our proposed pilot asks whether thirty students can identify their funding gap more accurately after ten minutes. We have a working simulator; the partnership and impact still need testing.

**Show:** the tree in **ES** or **FR** with the matching voice; *Make it mine* with the student's own grant or rent (*"My rent would be CHF 750/month"*); the Nora case in [`docs/impact/README.md`](impact/README.md). Say clearly that ESN has not been contacted.

## Q&A cheat sheet

All figures: `python scripts/pitch_figures.py`.

### UBS scorecard questions

**Which assumptions matter most?**
The engine ranks them per node: a deterministic tornado over each assumption's sourced range, shown under *What would have to be true*. Each moves the master's 10-year net worth by:

| Assumption | Effect on 10-year net worth |
|---|---:|
| Salary after the master's | CHF 106,058 |
| Studio rent | CHF 61,365 |
| Real wage growth | CHF 53,939 |
| Income-tax level | CHF 28,772 |
| Student-job income | CHF 24,615 |

Any of them can be edited, and the tree recomputes. A user's own condition (*Make it mine*) is the personal version of the same idea.

**How does a decision change the state?**
A decision is a list of interventions on the monthly plan:

- set, add or multiply income, rent or costs over a window, in CHF or EUR;
- a gross salary, which goes through the payroll layer;
- one-off costs and incomes;
- a new loan, or a change to an existing loan;
- a move of tax residence;
- a pillar 3a contribution;
- a change to an assumption on that branch only.

A child applies on top of its ancestors, and a user's condition is appended to the node it patches. Example: the study loan adds CHF 15,000 of cash in month 0 and CHF 300 a month of repayments from month 25. That moves the gap from CHF 18,553 in month 7 to CHF 3,538 in month 21.

**How did you verify it?**

1. It reproduces the UBS starter kit's three scenarios exactly.
2. Six live checks pass, 6/6, in the *Verified* panel: 9 accounting identities on all 40 nodes (largest error CHF 0.00), reproducibility, monotonicity, isolation, the UBS kit, and re-simulated thresholds.
3. The pytest suites for `core/` and `api/`, and the web unit tests (pass counts from `scripts/pitch_figures.py --tests`).
4. Payroll rates and tax tables come from official sources (ESTV, BSV, the BVG) and are marked verified; `core/bench` checks identities on 1,200 UBS ledgers.
5. Lumi's numbers are checked against engine tool outputs, and personal conditions against the user's own words.

**What happens when a constraint is violated?**

- Feasibility comes first: a funding gap or a broken hard limit makes the plan check "Needs financing" or "Does not hold", whatever the score.
- Negative cash is an unfunded need, never an automatic loan.
- Each constraint shows its margin, first breach month and months in breach: no funding gap, debt payments ≤ 33% of income, a 3-month buffer, and each goal.
- The levers, the children and the user's own conditions show what would fix it. A loan alone narrows the gap; with the scholarship, the loan branch holds.

**What would you improve next?** (from the ranked list in `core/ENGINE_AUDIT.md`)

1. Combined decisions and two-lever surfaces ("master's *and* share a flat"). Lluc is building these tonight.
2. Tax arrears timing, and unemployment eligibility rules.
3. Inflation per category (health premiums, rents).
4. Correlated shocks in the optional lens.
5. Tests on real, messier documents.
6. An ESN pilot measuring whether students can explain their funding gap.

### Other likely questions

- **"What about 3a?"** It's a lever. On *Start working*, CHF 604.83 a month (the CHF 7,258 yearly cap) raises 10-year nominal net worth from CHF 125,605 (cash) to CHF 151,820 and saves CHF 22,745 of tax. Only CHF 75,521 stays liquid, and the report says so.
- **"Taxes?"** Official ESTV 2026 effective rates for 12 cities × single / couple / family, and moves of residence. Abroad uses one assumed rate, flagged unverified.
- **"Can a user's sentence inject numbers?"** No. Personal conditions accept only numbers found in the user's words, within each lever's range, and ask one question when something is missing. The agent also has a scope gate and an injection guard.
- **"Isn't this just a spreadsheet?"** A spreadsheet gives one path. Here, 40 decision nodes recompute lazily, with stress tests, break-evens and reverse stress on every node. The user can add their own conditions by voice, and a guide explains each number without inventing any.
- **"Why is Monte Carlo off?"** It reads as a forecast. It is an optional lens, labelled "not real-world probabilities".
- **"Why not use the frontier model for documents?"** It costs 154× more for 1.7 points of accuracy.
- **"Is Lumi giving advice?"** No. It never recommends, and the agent drops sentences that do.
- **"Is the data real?"** No. Alexia and the profiles come from the UBS kit (synthetic). The documents are rendered by our generator with invented names and IBANs.
- **"What did you build this weekend?"** Everything in `core/`, `api/`, `multimodal/` and `web/`. See the README, *What we built at LauzHack*.
