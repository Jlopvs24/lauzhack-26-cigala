# QA report: third pass (thread 9)

Date: Sat 21 Nov 2026, 21:00–21:30. Tested the **running** app: web http://127.0.0.1:5175 (main checkout, master **991f129**, then a89c34e after the auto-pull) and API http://127.0.0.1:8000 (restarted 22:08 from master).
Browser: headless Edge (Playwright), muted, one at a time. Desktop 1440×900 light, EN. Phone 390×844 (touch, DPR 2), dark, **ES**.

**LLM budget.** 1 call, and it was unavoidable: opening the full path report fires `/api/report/summary` (qwen3.6-35b-a3b, $0.0002). I made no chat or extract calls. Make it mine used only the rules fast path; `/usage` stayed at 1 qwen call through every personalize step.

**Not tested.** #87 (Lluc's Pessimistic/Neutral/Optimistic weather rail) had not landed on master during this pass, so I tested the old weather panel.

## Summary (third pass)

| ID | Sev | Area | Finding | Owner | Status |
|---|---|---|---|---|---|
| P1-7 | P1 | Compare / drawer | When the compare bar is showing, it covers the report drawer header. The drawer's × Close lies under the bar's "Compare" button (elementFromPoint at the × returns `.cmp-bar-go`), so clicking × opens the comparison instead of closing the drawer. The bar also hides the drawer's "BRANCH n / title" | thread 10 + 6/7 | Open |
| P1-8 | P1 | Phone | Branch cards overlap each other. Root: "Irse al extranjero" covers the bottom of "Hacer un máster" (about 125×46 px). Level 2: "Préstamo de estudios" covers "Solo el trabajo de estudiante", whose title can't be read. `data-layout-obstacle` keeps cards off panels, but not off each other | thread 6 | Open |
| P1-9 | P1 | Phone | The "Atrás" (Back) button (`.nav-back`, y≈653) sits under the narration bubble: elementFromPoint returns the bubble's `<p>`, so you can't go back up a level on a phone | thread 6 | Open |
| P2-10 | P2 | Demo ops | The 2-minute auto-pull of master triggered a full Vite reload during the test, which dropped the page back to the portal and lost all state. Turn auto-pull off before the demo | thread 0 | Note |
| P2-11 | P2 | Navigation | Once in the tree there is no in-app way back to the portal (`setStarted(false)` never appears), so "voice stops when going back to the portal" can't happen. The lifecycle handlers (pagehide/popstate/hashchange) exist in `voice.js` | thread 6 | Note |
| P2-12 | P2 | Report | Every time the full path report opens it costs one LLM call (`/api/report/summary`) | thread 2/7 | Note (budget) |
| P2-13 | P2 | i18n | In ES, the card goal name is still English: "Career transition: faltan CHF 453". Lumi's aria-label "Lumi, your guide" is also English | Lluc/thread 6 | Open |
| P2-14 | P2 | Compare | In the spec sheet, "highest" gets the same blue shade whether higher is better (net worth) or worse (funding gap). The chart's green "Repay fast" line hides the orange "Do a master's" line (values nearly equal) | thread 10 | Open |

### Re-checks of earlier findings
- **P1-1 Roots — FIXED.** Profile Marco / Zurich / 24 / cash 3,000 / net 2,600 / rent 1,300 / other 900 (typed in the form, no extraction). The narration says "This is Marco today. Marco keeps the current life: net income of CHF 2,600 a month and CHF 2,200 of monthly costs (rent CHF 1,300), starting with CHF 3,000 in cash. Plan check: holds, below the buffer target…". Level 1 differs from Alexia's: Start working 1.1 months buffer; master's gap 9,274 from m2; abroad gap 4,102 from m1, NW 9,065.
- **P1-4 Voice on hidden tab — FIXED.** After a simulated `visibilitychange` to hidden, no new audio started and no mouth-level events fired over 12 s.
- **P1-6 Compare not mounted — FIXED** (see item 2).
- **P1-3 Phone header — FIXED.** At 390 px in ES, every header control is on screen, wrapped onto two rows.
- **P1-5 Weather covers cards — FIXED on desktop.** No overlap between the weather panel and any card (obstacle check).
- **P2-2 Remove from scene — partly.** There is still no remove control in the scene itself. But the **Report drawer** (header "Report" button) lists "Your conditions" with ×, and it works with no API call. Only the full path report costs an LLM call.

## Results by item

1. **Layout / Lumi — pass (desktop).** Lumi is docked bottom-right above the chat line from the start (76×91 at 1336,715). "Open conversation" merges Lumi, history and input into a right-hand panel (1008–1440), and the cards move left with no overlap. Lip sync: 462 non-zero `lumi:level` events while Kokoro played; no levels during the gaps between sentences; the last level is 0 at 57.74 s, right after audio ended at 57.69 s.
2. **Compare — pass, with P1-7.** Each card has a "+" pin (it turns to ✓ when pressed). The bar shows "2 of 4 selected · Clear · Compare". The comparison page has a chart, the spec sheet and "Show only differences" (34 → 28 rows). From a leaf report (Do a master's → Study loan → Repay fast): "+ Add to comparison" → "In comparison · Compare (3) →". The comparison opens **over** the report with 3 columns, and × goes back to the report. Note: the button copy is "In comparison · Compare (3)", not "Added · Compare (n)". Pins are hard to click for automation because the cards keep moving (they sway); a human can click them.
3. **Profile-aware tree — pass** (see P1-1 above).
4. **Make it mine — pass.** "I'd get a CHF 600/month scholarship": proposal in **0.2 s**, 0 LLM calls, "+CHF 600/month income, months 1–24".
   - Apply to this branch: Student job only 18,553 m7 → **3,914 m13**. Study loan: no gap, buffer 3.8 (m25), lowest cash 11,113. "YOUR CONDITIONS" badges show. Same as the second pass.
   - Remove (Report drawer ×): every card goes back to the original values.
   - Add as a new option: a 4th child "Scholarship" (YOUR BRANCH), gap 3,914 from m13, NW 115,944, "+CHF 13,348 vs before". Same as the second pass. Removing it takes the tree back to 3 children.
5. **Voice — hidden tab pass; going back to the portal is not possible** (P2-11).
6. **Weather (old panel) — pass.** On the Repay fast leaf, Job loss moves both siblings from a 3,538 gap from m21 to **5,751 from m18**.
7. **npm test** on 991f129: **73/73 pass**, 0 fail (the stale ES/FR/DE row failure Lluc saw on 0239e2c is gone).

---

# QA report: second pass (thread 9)

Date: Sat 21 Nov 2026, 19:55–20:35. Tested the **running** app: web http://127.0.0.1:5175, API http://127.0.0.1:8000.
Browser: headless Edge (Playwright), muted, one at a time. Desktop 1440×900; phone 390×844 (touch, DPR 2); light and dark (`prefers-color-scheme`).

**Build under test.** I started on :5175 served from thread 6's worktree (`6-cards-wt`, detached at 9c83c39 / #67). From 20:15, thread 0 repointed :5175 to `origin/master` f552200 (with #70, #71, #74, #75, #76). Every result marked **[f552200]** was re-tested on master.

**LLM budget.** I used 4 of 4 calls: 3 × `/tree/personalize` (one of them timed out in the UI) and 1 × `/profiles/extract`. After #75, every personalize test went through the rules fast path; `/usage` showed no new LLM calls. To test the confirm/clarify UI without more calls, I replayed **real** API responses recorded earlier with Playwright route interception. I mark those steps as "replayed".

The first pass already covered tree navigation, narration, languages, report, Verified 6/6 and chat. I did not repeat them. Known issues already being fixed are not re-reported: cards under the header, chat dock over the report, leaf framing/mask, slow Kokoro, no German voice, number format mix.

## Summary

| ID | Sev | Area | Finding | Owner | Status |
|---|---|---|---|---|---|
| P0-1 | P0 | Make it mine | `/tree/personalize` took 45.9 s; the UI aborted at 30 s with "signal timed out" | thread 2 + 7 | **Fixed in f552200, verified** (0.4 s, no LLM; #74 UI fallback works) |
| P1-1 | P1 | Roots | After "Apply profile", Lumi still says "Alexia keeps her current life: student job of CHF 1,200…", and all three first branches show Alexia's exact numbers | thread 2 + Lluc | Open |
| P1-2 | P1 | Phone | Make it mine panel overflows the right edge on 390 px: "Check it" and × are cut off | thread 7 (+6 for layout) | Open |
| P1-3 | P1 | Phone | Header overflows on 390 px: "Sound on" and "Report" are off-screen (Report at x=373, w=62) and cannot be reached | thread 6 | Open |
| P1-4 | P1 | Voice | Lumi keeps talking when the tab is hidden. New sentences keep starting; no `visibilitychange`/`pagehide` handling | thread 6 | Open |
| P1-5 | P1 | Weather | The weather panel (top-left) covers the "Start working" card at the root, and covers "Student job only" on level 2 | thread 6 | Open [f552200] |
| P1-6 | P1 | Compare | #76 is not mounted in the app: no `CompareRoot`, card strip, pins or "Compare these options" in `main.jsx`/`PathReport`. It only works on `/src/compare/demo.html` | thread 6 + 7 | Open [f552200] |
| P2-1 | P2 | Report vs cards | Report "Net worth in 10 years" is nominal (CHF 113,330), while cards and compare use today's prices (CHF 102,596) for the same node | thread 7 | Open |
| P2-2 | P2 | Make it mine | A condition can only be removed from inside the Report ("Your conditions" ×). The scene has no remove control | thread 7 | Open |
| P2-3 | P2 | Make it mine | Copy mismatch: the panel says "Add as a new option", the report list says "new branch" | thread 7 | Open [f552200] |
| P2-4 | P2 | Voice | Opening the conversation panel does not stop the narration (a new sentence started within 3 s). Report, Verified, Sound off and Make it mine do stop it | thread 6 | Open (maybe intended) |
| P2-5 | P2 | Roots | Fields not found in the document keep Alexia's values (age 20, cash 8,000, rent 900, other 600), so the profile mixes two people | thread 6/2 | Open |
| P2-6 | P2 | Roots | Native file input follows the browser locale ("Elegir archivos / No se ha seleccionado ningún archivo") in an English UI | thread 6 | Open |
| P2-7 | P2 | Weather | Market crash has no effect on Alexia's three first options (net worth identical: no invested savings), so the toggle looks broken in the demo. Recession moves net worth only about 4k and no plan level changes | Lluc (demo data) | Note |
| P2-8 | P2 | Compare | Stress row shows "–" for every column but "Breaks under: none", which reads as robust; "holds if started within 0 months" is awkward copy | thread 10 | Open |
| P2-9 | P2 | Verified | Panel header says "ran in 93426.5 ms" (93 s); it looks slow even if it runs only once at startup | thread 2 | Note |

## Details

### P0-1 Make it mine timed out (fixed, verified)
- **Repro (9c83c39 web, old API):** Alexia → Do a master's → "+ Make it mine" → "I'd get a CHF 600/month scholarship" → Check it.
- **Actual:** after 30 s the panel showed "signal timed out" with Cancel / Try again. A direct `curl` of the same request returned 200 after 45.9 s (`latency_ms 45893`, qwen/qwen3.7-flash), and the proposal was correct. `web/src/api.js` aborts every request at 30 s.
- **Re-test [f552200]:** proposal in 0.4 s, `/usage` unchanged (rules fast path). With the request held open (route never fulfilled), the panel showed "Lumi is reading your situation… Cancel". At about 20 s it switched to "Lumi took too long to read that. Try again / Enter the numbers". "Enter the numbers" opens a form prefilled from the text (Extra income, 600, per month, from month 1). **Pass.**

### Make it mine: results (step 6)
Node "Do a master's" and its children, CHF:

| | Before | Patch "Apply to this branch" (+600/month, months 1–24) | After removing |
|---|---|---|---|
| Do a master's (report) | gap 18,553 from m7, NW 113,330 | gap 3,914 from m13, NW 128,074 (nominal) | gap 18,553 from m7, NW 113,330 |
| Student job only | gap 18,553 m7, buffer −8.7 | gap 3,914 m13, buffer −1.8 | identical to before |
| Study loan CHF 15,000 | gap 3,538 m21, NW 101,432 | no gap, buffer 3.8 (m25), NW 114,801 | identical to before |
| Part-time master's 60% | buffer 2.6, goal m37 | buffer 2.6, NW 117,508 | identical to before |

- Arithmetic check: 600 × 24 = 14,400; the gap falls 18,553 → 3,914 (−14,639), and NW rises 14,744 (nominal). Consistent.
- Marking: every re-grown child gets a "YOUR CONDITIONS" badge; Lumi's narration updates ("cash runs short from month 13").
- Report with a patch: **no 422**. The report loads via `/tree/explore` and lists the condition in its assumptions and under "Your conditions" with ×. Removing it there restores every scene and report number exactly. [same result on f552200]
- **New option mode [f552200]:** "Add as a new option" adds a fourth child, "Scholarship": gap 3,914 from m13, NW 115,944 (today's prices), "+CHF 13,348 vs before" (= 115,944 − 102,596, correct). Same figures as patch mode, so the earlier "new branch ignores the master's interventions" bug is **fixed**. API cross-check with `custom_nodes` 2.c1 gives the same. Removing it from the report removes the card.
- **No number** ("I would get a scholarship"): the API asks "How much is the scholarship per month, and for how many months?" (5 s, LLM). The UI (replayed) shows "ONE QUESTION FIRST" with an answer field. Answering resends `text + answer` with `history`. **Pass.**

### P1-1 Roots: the restarted tree is still Alexia's
- **Repro:** Portal → "Start with your own roots" → upload `data/synthetic/docs/P00076-payslip.pdf` → "Extract into the form" (19.5 s) → name **Elena**, income **533.09**. Exact match with the manifest truth (net 533.09); confidence 85% / 100%. → "Apply profile and restart tree".
- **Expected:** the narration and branches describe Elena with CHF 533/month.
- **Actual:**
  - Narration: "This is Elena today. Alexia keeps her current life: student job of CHF 1,200 and CHF 1,500 of monthly costs." The root `description` is static text from the tree (`/tree/expand` returns it unchanged with a custom profile).
  - Start working, Do a master's and Move abroad show **exactly** Alexia's numbers (gap 18,553 m7, NW 48,039, …). Only the "vs before this choice" deltas change (+CHF 119,229, +58.1 months). The branch interventions `set` income, so the user's income never reaches any branch. Only the root changes.
- **Owner:** thread 2 (descriptions from the profile, not static) and Lluc (branch interventions relative to, or derived from, the profile).
- Not tested: the text and dictation paths of Roots (they would have cost an LLM call).

### P1-2 / P1-3 Phone 390×844
- No horizontal page scroll (scrollWidth 390). The portal, tree, cards, Lumi bubble, report drawer and chat panel are readable, in light and dark.
- **P1-2:** with the Make it mine panel open, its right edge is off-screen: the "Check it" button is cut in half and × is hidden. Cancel still works.
- **P1-3:** the header row (language, Dark, Sound, Verified/6/6, Report) is wider than 390 px. "Report" sits at x=373 and can't be tapped. In some states "Verified 6/6" collapses to "6/6" and "Sound on" is clipped. The only way to the report on a phone is a synthetic click.
- Also on phone: the Lumi bubble covers the Back button at level 2.

### Dark mode
Every screen checked on desktop: portal, root tree, level 2, Make it mine panel, report drawer, chat panel, Verified panel, Roots. Phone checked: tree and chat. All are coherent: dark surfaces, readable text, consistent buttons. The app follows `prefers-color-scheme`, and the toggle reads "Light". Only issue: the native file button in Roots stays light grey (P2-6). **Pass.**

### P1-4 Does Lumi keep talking after leaving?
`HTMLMediaElement.play` was instrumented (the voice uses `new Audio(blob)` per sentence from `/voice/tts/stream`).
- **Tab hidden** (visibilityState → hidden + `visibilitychange`): **keeps talking.** Three more sentences started 0.5 s, 2.5 s and 5.9 s after hiding. `web/src/scene/voice.js` and `main.jsx` have no `visibilitychange`/`pagehide` listener. In a real browser, a background tab keeps playing audio. **Confirmed.**
- **Back to the portal:** there is no in-app route back to the portal (the logo is not a link). Reload or closing the tab unloads the page and the audio stops.
- Stops correctly when: navigating to another node (`go()` → `stop()`), opening Report, opening Verified, Sound off, opening Make it mine.
- Does **not** stop when the conversation panel opens (P2-4).
- **Fix suggestion (thread 6):** `document.addEventListener('visibilitychange', () => document.hidden && voice.stop())`, plus `pagehide`.

### Weather control [f552200]
- The panel appears at top-left under the header, with chips, "Clear sky", "Starts in month 13" and "Default length".
- **Recession** → one `/tree/expand` and the cards recompute: Do a master's gap 18,553 → **18,620**; Move abroad "career transition missed by CHF 453" → **4,251**, NW 48,039 → **43,396**. Legend and Lumi: "If a recession starts in month 13: 1 of 3 options still holds." **Clear sky** restores every number exactly. **Pass.**
- API cross-check (no LLM): recession m0–24 lowers 10-year NW by about 8.8k on every first option; job loss lowers it 2–6k; **market crash changes nothing** for Alexia, who has no investments (P2-7).
- P1-5: the panel covers cards (see the table).

### Compare (#76) [f552200]
- **Not mounted in the app** (P1-6): `main.jsx` has no `CompareRoot`/`CompareOptionsButton`/`cardCompareHTML`/`pinHTML`, and `PathReport` has no `AddToCompare`. The README lists these mount points for threads 6 and 7.
- Tested on `/src/compare/demo.html` against the live API:
  - Comparative cards: rank ("1 of 3"), "+CHF 15k vs Student job only", "no funding gap · 2 others have one". Figures match the engine (102,596 / 101,432 / 117,508 in today's prices).
  - "Compare these options" opens the spec sheet: chart (net worth / cash, funding-gap band), "Show only differences", rows for outcome, own impact, what would have to be true (smallest change +CHF 762/month = Lluc's figure, CHF 18,531 now), timing, break-even. Calls: `/tree/compare`, `/tree/explore` ×3, `/tree/smallest_change` ×3, `/tree/timing_scan` ×3, all 200.
  - Pins: + on "Move abroad" (level 1) and "Study loan" (level 2) → bar "2 of 4 selected" → Compare → two columns across branches. **Pass.**
- P2-8: copy in the stress and timing rows.

## Not covered
Text and dictation in Roots, live chat proposals into Make it mine, the weather sliders (start month, length), and other languages for the new features. All were limited by the LLM budget or time.
