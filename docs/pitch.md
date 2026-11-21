# Pitch and demo script

**Arbor: explore your futures before you live them.** Lumi is the light that lives in the tree. One story, Alexia, told in under three minutes, hitting UBS (main), AXA and IMC. The climax is **Make it mine**: Alexia adds her own condition and the branch re-grows. Booth variants and a Q&A cheat sheet follow.

> **Never type an engine figure by hand.** Every figure below comes from `python scripts/pitch_figures.py` (engine `core-1.1`, Alexia's demo profile, default assumptions, Sat 21 Nov 22:06, master `991f129`). **Re-run the script before rehearsing and before submitting**, and update anything that moved here, in the README and in `docs/submission/`. Lumi's lines are produced by `web/src/scene/narration.js` from engine fields, not by an LLM; the script prints them too.

## Before you start (3 minutes)

- Chrome or Edge, full screen, at `http://127.0.0.1:5175`. Language **EN**. Sound **on**: the first click unlocks audio.
- The API is running on port 8000, restarted on current `master` (since #92 the default LLM is `qwen/qwen3.6-35b-a3b`). `/health` shows `"engine": "core"`, `"personal_conditions_supported": true` and Kokoro `available: true`.
- The header shows the **Verified 6/6** badge. The weather rail on the left is on **Neutral**.
- Lumi is docked at the bottom right, above the chat line, and her mouth moves when she speaks. Opening the conversation moves her into the chat panel.
- **Make it mine** appears on the current branch. Try the scholarship sentence once: since #75 it is parsed by deterministic rules (0.02 s, no model), so it works without the LLM.
- Reload the page before you start: since #121 a reload starts fresh, with no previous chat, pins, personal conditions or Live consent.
- Optional AXA beat: the three demo documents are on the desktop (`data/synthetic/docs/P00001-payslip.jpg`, `P00001-bank_statement.pdf`, `P00001-rental_contract.jpg`). **Do this beat only if extraction takes 10 s or less on the demo laptop.** On the shared API on Sat 20:40 it took 57–74 s per photo.
- Rehearse at least twice against a timer.

## Main demo: 2:50

| Time | Screen and clicks | Say | Lumi says (aloud) |
|---|---|---|---|
| **0:00–0:15** Hook (IMC) | Start portal: *"Every choice grows a different tree."* | "This is Alexia. She's 20, studies in Lausanne and has CHF 8,000 saved. Should she start working, do a master's or move abroad? She can't afford a financial adviser, and a chatbot would make up numbers. So we built Arbor: a financial twin she can explore, and make her own." | – |
| **0:15–0:28** Roots (AXA) | **Try the demo: Alexia**. The camera rises from the roots to the tree. (Optional, if extraction is fast: **Start with your own roots** → **Add documents** → the three `P00001-*` files → **Read my roots** → point at *Source · extraction confidence* → **Grow my tree**.) | "Her roots can come from a payslip photo, a bank statement and a lease, read on this laptop with local OCR and a small model. A vision model is called only if a check fails: 97.7% accuracy at 1/154th of the frontier model's cost." | (root line, may be cut by the next click) |
| **0:28–0:50** The hook (UBS) | Click the **Do a master's** limb; the camera flies in. Point at its card: plan check and *what it trades*. | (Stay quiet while Lumi speaks, then:) "Under the UBS starter kit's own cash-only assumptions we reproduce its result exactly: the master's runs out of cash in month 7. Then we make it Swiss: the official 2026 income tax of her city, pillar 3a, and payroll for gross salaries." | *"Do a master's. Two years of master's with a student job, then a better-paid job. Plan check: needs financing. In this scenario the cash runs short from month 7. From here: student job only, study loan of CHF 15,000 or part-time master's with a 60% job. The other branches stay in grey so you can compare."* |
| **0:50–1:10** What would have to be true (UBS) | **Report** (header) → *What would have to be true* → *What would fix it*. | "We don't forecast; we ask what would have to be true. Her salary after the master's matters most. Against starting work, the break-even is CHF 4,960 a month, and starting a year later costs 17,628. But no salary fixes month 7: that's a cash problem. What would fix it: CHF 762 a month more, or 18,531 once." | – (Lumi stays quiet over reports) |
| **1:10–1:50** **Make it mine (climax)** | **Esc**. On *Do a master's*: **Make it mine** → **Speak** (or type) *"I'd get a CHF 600 a month scholarship during the master's"* → **Check it** → *Here is how I understood it*: **+CHF 600/month income, months 1–24**, *"Every number here comes from what you said; nothing is invented."* → **Apply to this branch** → **Confirm**. The branch re-grows. | "But Alexia knows something the model doesn't: she'd get a scholarship. She just says it. Her words become one change, using only numbers she said. She confirms, and the engine re-grows this branch and everything under it. The gap shrinks from CHF 18,553 in month 7 to 3,914 in month 13. And the study loan, which needed financing a minute ago, now holds." | – |
| **1:50–2:12** Weather and comparison (UBS) | On the master's children: on the weather rail pick **Pessimistic** and read the card changes and legend aloud, then **Reset to neutral**. Then **Compare these options** → the comparison page. | "Weather is what she doesn't choose. Here, a pessimistic outlook: every card recomputes and says what it does to her. With the loan she keeps no funding gap and meets her goals in all four stress scenarios we test, though inflation or a job loss would push her below the three-month buffer. And she can put any options side by side." | (Lumi reads the weather legend) |
| **2:12–2:32** Her path report (UBS) | **Study loan of CHF 15,000** → **Repay over about 5 years** → **Open your report**: the brief, *her conditions*, *what would fix it*, *room to move*, *if you start later*, the stress table, *Validation and reproducibility*. Click **Verified 6/6**. | "Her report, with her own condition in it, ready as a PDF, and every result carries a trace id. Six checks run live on the engine: accounting identities on all 40 nodes, reproducibility, monotonicity, isolation, the UBS kit, and re-verified thresholds. They check the arithmetic and the method, not the future." | *"Study loan of CHF 15,000. … Plan check: holds. In this scenario the cash never runs out. …"* (on the way) |
| **2:32–2:50** Close (IMC) | Back on the tree. Optional: switch to **ES**, and Lumi re-reads the node in Spanish with a Spanish voice. | "Lumi explains and never recommends, and her default model has open weights, so a bank could run it on its own servers. Arbor is free, works in four languages and listens to your own words. A student-network volunteer could run it in ten minutes, before a student signs a lease. Arbor: explore your futures before you live them. Thank you." | – |

**If something breaks:**

- **The proposal asks a question instead** (for example *"For how many months?"*): answer *"for the two years of the master's"*. That also shows it never guesses.
- **Make it mine returns a question with no proposal** for an unusual phrasing (it needed the LLM, which is unreachable or over budget): use the scholarship sentence exactly as written, which the rules handle.
- **Extraction is slow:** skip it (see *Before you start*) and say the AXA line over the tree.
- **No audio:** read Lumi's bubble aloud yourself, or use **Sound off**; the bubble text is identical.
- **Leftover conditions or pins from a rehearsal** change the cards: reload the page.
- **Make it mine is slow to reach:** say the sentence to Lumi in the chat instead. A statement changes the branch directly through the same rules and the engine (about 0.1–1 s); a *"What if…"* question grows a new branch.

## Booth variants (30–40 s each)

### UBS booth

> We centre conditional scenarios; Monte Carlo is an optional simulation lens, not a forecast. Under your starter kit's own cash-only assumptions, our engine reproduces its three scenarios to the franc. Then we made it Swiss: official 2026 income tax for twelve cities and three household types, pillar 3a, and payroll for gross salaries. On each branch it asks what would have to be true, and what would fix it. And the twin becomes yours: say "I'd get a CHF 600 scholarship", confirm, and that branch re-grows. A funding gap is never hidden behind a score. Six checks run live, and Lumi's default model has open weights, so you could host it yourself.

(112 words, about 45 s)

**Show:** the master's card → Report → *What would have to be true* / *What would fix it* → **Make it mine** with the scholarship → **Compare these options** (or **+ Add to comparison** from a report) → **Verified 6/6**. If asked about privacy: README, *Privacy: what runs where*.

### AXA booth

> We use the smallest thing that works at every step. A payslip photo is read by local OCR and a small model with an 800-token budget. Deterministic checks follow, and only if one fails does that document go to a cheap vision model. On 60 synthetic Swiss documents that is 97.7% field accuracy against 99.4% for the frontier model, at 154 times lower cost. "Make it mine" parses common sentences with plain rules, at zero cost, and calls a small open-weight model only for the rest. Lumi's voice is local Kokoro. The session's API cost is shown, and a daily budget guard falls back to templates.

(106 words, about 40 s)

**Show:** the benchmark table in [`multimodal/benchmark/RESULTS.md`](../multimodal/benchmark/RESULTS.md); *Session API cost* in the chat panel; the roots review with source and confidence per field.

### IMC booth

Lluc's sourced 96-word draft from [`docs/impact/README.md`](impact/README.md), unchanged:

> A grant is not a budget. ESN's survey found that more than a third of students reported insufficient funding for living costs. Our financial twin lets a student compare rent and funding choices, see when cash runs out, and inspect every assumption. The engine calculates; Lumi explains. An ESN volunteer could offer this free before a student signs a lease, then refer unresolved gaps to the university. Our proposed pilot asks whether thirty students can identify their funding gap more accurately after ten minutes. We have a working simulator; the partnership and impact still need testing.

**Show:** the tree in **ES** or **FR** with the matching voice; *Make it mine* with the student's own grant or rent (*"My rent would be CHF 750/month"*); with their own roots, the tree adapts to their income and costs (#77); the Nora case in [`docs/impact/README.md`](impact/README.md). Say clearly that ESN has not been contacted.

## Q&A cheat sheet

All figures: `python scripts/pitch_figures.py`.

### UBS scorecard questions

**Which assumptions matter most?**
The engine ranks them per node: a deterministic tornado over each assumption's sourced range, shown under *What would have to be true*. Each moves the master's 10-year net worth by:

| Assumption | Effect on 10-year net worth |
|---|---:|
| Salary after the master's | CHF 106,058 |
| Real wage growth | CHF 53,939 |
| Studio rent | CHF 40,911 |
| Income-tax level | CHF 28,772 |
| Student-job income | CHF 24,615 |

Any of them can be edited, and the tree recomputes. The report's *room to move* heatmap moves two of them at once. A user's own condition (*Make it mine*) is the personal version of the same idea.

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

1. Under the starter kit's cash-only assumptions, the engine reproduces its three scenarios exactly. That is a check of the cash arithmetic, not of the Swiss-world results.
2. Six live checks pass, 6/6, in the *Verified* panel: 9 accounting identities on all 40 nodes (largest error CHF 0.00), reproducibility, monotonicity, isolation, the UBS kit, and re-simulated thresholds. They establish those numerical properties, not predictive validity.
3. The pytest suites for `core/` and `api/`, and the web unit tests (pass counts from `scripts/pitch_figures.py --tests`).
4. Statutory payroll rates (AHV/IV/EO, ALV, BVG thresholds and credits) and the ESTV tables come from official sources. Insurer and plan inputs (NBU 1%, the employee's BVG share) are explicit unverified assumptions. Parameters were calibrated against public Swiss targets only (`core/bench/OPTIMISATION.md`), and `core/bench` checks identities on 1,200 UBS ledgers.
5. Lumi's agent checks larger numeric claims against engine outputs or user input and falls back to a template when that fails. This is a guard, not a proof of every claim. Personal conditions use only numbers in the user's own words.

**What happens when a constraint is violated?**

- Feasibility comes first. A funding gap makes the plan check "Needs financing", another broken hard limit or a missed goal makes it "Does not hold", and a buffer-only shortfall makes it "Holds, below the buffer target", whatever the score.
- Negative cash is an unfunded need, never an automatic loan.
- Each constraint shows its margin, first breach month and months in breach: no funding gap, debt payments ≤ 33% of income, a 3-month buffer, and each goal. The 33% and the 3 months are editable rules of thumb.
- *What would fix it* answers directly. For the master's, the smallest change that closes the gap is +CHF 761.93 a month of income, CHF 765.54 less rent a month, or CHF 18,531.27 once in month 0. A loan alone narrows the gap; with the scholarship, the loan branch holds.

**What would you improve next?** (from `core/ENGINE_AUDIT.md` and `core/README.md`)

1. Abroad: city-specific living costs, EUR inflation and FX volatility (today: constant editable EURCHF, ±10% franc stress, Swiss inflation on EUR amounts).
2. Run the open-weight LLM on our own server (`LLM_BASE_URL`, no fallbacks), so no conversation leaves it. It is configured, not done in the demo.
3. Tax arrears timing (tax is paid in the same month today), and unemployment eligibility rules.
4. Inflation per category (health premiums, rents).
5. Correlated shocks in the optional lens.
6. Tests on real, messier documents.
7. An ESN pilot measuring whether students can explain their funding gap.

### Other likely questions

- **"What about 3a?"** It's a lever. On *Start working*, CHF 604.83 a month (the CHF 7,258 yearly cap) raises 10-year nominal net worth from CHF 125,605 (cash) to CHF 148,865 and saves CHF 22,745 of tax. Only CHF 75,521 stays liquid, and the report says so.
- **"Taxes?"** Official ESTV 2026 effective rates for 12 cities × single / couple / family, and moves of residence. Abroad uses one assumed rate, flagged unverified.
- **"Does 'holds in 4 of 4' mean it's safe?"** No. It means no funding gap and every dated goal met under each of four selected stress scenarios. The buffer target can still fail (it does for the loan under inflation and job loss), and real risks are not limited to these four.
- **"Is the 4% return verified?"** It is a prudent team assumption informed by historical Swiss returns (Pictet), after fees. It is not an empirical verification of future returns, and it is editable.
- **"Can a user's sentence inject numbers?"** No. Personal conditions accept only numbers found in the user's words, within each lever's range, and ask one question when something is missing. The agent also has a scope gate and an injection guard.
- **"Does Lumi check every number it says?"** It checks larger numeric claims (100 or more) against engine outputs or the user's input and falls back to a template if one fails. It doesn't check small numbers, which metric a number belongs to, or qualitative statements. The financial results themselves come only from the engine.
- **"Isn't this just a spreadsheet?"** A spreadsheet gives one path. Here, 40 decision nodes recompute lazily, with stress tests, break-evens, what would fix it and a start-later scan on every node. The user can add their own conditions by voice and compare options across branches.
- **"Why is Monte Carlo off?"** It is a simulation, not a forecast, and we keep it secondary so attention stays on choices. It is an optional lens, labelled "not real-world probabilities".
- **"Why not use the frontier model for documents?"** It costs 154× more for 1.7 points of accuracy.
- **"What is Lumi Live?"** An optional realtime voice call (Gemini Live). It starts only after a consent step, because the voice and this branch's engine results then go to Google. The default chat stays on the open-weight model.
- **"Is Lumi giving advice?"** No. It never recommends, and the agent drops sentences that do.
- **"Where does my data go? Could a bank run this in-house?"** The engine needs no model, Kokoro speaks locally and OCR runs on the device. Lumi's default LLM is Qwen3.6-35B-A3B with open weights (Apache-2.0); a configuration change (`LLM_BASE_URL` and the model name) points it at a self-hosted server, for example on a bank's premises. In the demo it is served through OpenRouter, not locally. Proprietary models (qwen3.7-flash, Haiku, and Gemini Flash-Lite for failed document checks) are fallbacks only. Common personal conditions are parsed by rules and never reach a model.
- **"Is the data real?"** No. Alexia and the profiles come from the UBS kit (synthetic). The documents are rendered by our generator with invented names and IBANs.
- **"What did you build this weekend?"** Everything in `core/`, `api/`, `multimodal/` and `web/`. See the README, *What we built at LauzHack*.
