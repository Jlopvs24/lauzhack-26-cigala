# Submission form (ready to paste)

Submit at https://app.lauzhack.com/Participant. **One person** submits, then invites the teammate; the form stays editable until the deadline. Hard stop **Sun 22 Nov 12:00**. Rules: [`docs/challenges.md`](../challenges.md).

Character counts were computed with Python `len()` on the exact strings below, without the surrounding code fences. The descriptions quote no engine figures that can move, only the benchmark (fixed run) and facts about the method. If you add one, take it from `python scripts/pitch_figures.py`.

## Title (max 40 characters)

| # | Title | Characters | Why |
|---|---|---:|---|
| 1 | `Arbor – explore your futures` | 28 | Recommended. The product name and the core of the tagline; short enough to read in the main ranking. |
| 2 | `Arbor: explore your futures` | 27 | Same, with a colon if the platform mangles the en dash. |
| 3 | `Arbor – a financial twin for students` | 37 | Says exactly what it is, in UBS wording (financial twin). |

The product is **Arbor** (tagline: *Explore your futures before you live them*). The guide is **Lumi**, the light that lives in the tree. The repository keeps its name, `lauzhack-26-cigala`.

## Short description (max 100 characters)

| # | Short description | Characters | Note |
|---|---|---:|---|
| 1 | `Arbor: explore your futures before you live them. A financial twin for students.` | 80 | Recommended: the full tagline plus what it is. |
| 1b | `A financial twin for students: explore each life choice, add your own situation, watch it re-grow.` | 98 | Names the core value-add (personal conditions). |
| 2 | `Explore, don't predict: a verified financial twin that shows where each student life choice breaks.` | 99 | Echoes the UBS feedback. |
| 3 | `A cinematic tree of your financial future: each branch a decision, each number from a tested engine.` | 100 | Leads with the experience. |

## Long description (max 1000 characters): 994 characters

```text
Arbor is a financial twin for students, drawn as a tree of life. Branches are decisions, explored with a deterministic monthly engine: official ESTV 2026 income tax by city, pillar 3a, payroll for gross salaries, editable sourced assumptions, plan check, break-even, what would fix it, stress what-ifs and comparison. Under the UBS starter kit's own assumptions it reproduces the kit exactly; six live checks pass. Make it mine: say your own situation ("I'd get a CHF 600/month scholarship"); rules or a small model turn it into one change using only your numbers, you confirm, and the branch re-grows. Roots come from a questionnaire, voice or a payslip photo read by a frugal chain (local OCR, a small model, checks; vision only if a check fails): 97.7% accuracy, 154x cheaper than a frontier model. Lumi explains engine results in four languages, with a local voice and a self-hostable open-weight model, and never recommends. Free: a student network could offer it before a lease is signed.
```

Every claim traces to the repo:

- personal conditions: `api/README.md` (`/tree/personalize`) and `docs/contracts.md`;
- payroll (statutory rates plus explicitly assumed insurer and plan inputs), tax and pillar 3a: `core/README.md`;
- the starter-kit reproduction and the six checks: `core/validation.py`;
- the benchmark: `multimodal/benchmark/RESULTS.md`;
- the agent's numeric grounding guard (larger numbers only, not a proof of every claim) and the advice guard: `api/README.md`;
- the open-weight default model (Qwen3.6-35B-A3B, Apache-2.0), self-hostable with `LLM_BASE_URL` but served through OpenRouter in the demo: `api/README.md`, *Models & privacy*;
- comparison, weather on the tree and what would fix it: `web/src/compare/`, `web/src/weather/`, `web/src/report/`.

## Public link

`https://github.com/Jlopvs24/lauzhack-26-cigala`. The repo is **private** today; make it public only after the secret scan in [`checklist.md`](checklist.md).

## Challenges to tick

- [x] **UBS – AI Financial Twin** (main)
- [x] **AXA – Frugal use of Multimodal AI**
- [x] **IMC – Tech for Good**
- Main ranking: automatic, every project is in it.
- Do **not** tick Logitech, JetBrains, Nexthink, Scholé or SBB.

## Thumbnail brief (max 300 KB)

- **Content:** the photoreal tree at dawn from the web app's master still, with Lumi (the glowing guide orb) beside the trunk. One limb is lit (the chosen branch) and the others are greyed, as in the app. Optionally, a small card in the app's style shows the *Make it mine* chip: *"+CHF 600/month scholarship"*, to hint at money and personalisation.
- **Text on the image:** the title only, large and legible at 300 px wide. No logos of UBS, AXA or IMC, and no engine numbers that might change.
- **Source:** a screenshot of the start portal or of the tree (`web/public/tree/`, master still). Lumi's art is in `web/assets/character/guide/`. No new image generation is needed.
- **Format:** 1280 × 720 (16:9) JPEG or WebP, quality around 75. Check the size: `python -c "import os; print(os.path.getsize('thumb.jpg') // 1024, 'KB')"` must print 300 or less. If it is too big, resize to 960 × 540 or lower the quality.
- **Save as:** `docs/submission/thumbnail.jpg` and commit it.

## After submitting

- [ ] Invite the teammate (Lluc, `@llucliment`) to the project on the platform.
- [ ] Open the public link in a private window: the README renders, the screenshots load, and there are no 404s.
- [ ] Post the submission confirmation on the board.
