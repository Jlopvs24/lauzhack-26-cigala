# Submission form (ready to paste)

Submit at https://app.lauzhack.com/Participant. **One person** submits, then invites the teammate; the form stays editable until the deadline. Hard stop **Sun 22 Nov 12:00**. Rules: [`docs/challenges.md`](../challenges.md).

Character counts were computed with Python `len()` on the exact strings below, without the surrounding code fences. Re-count after any edit: `python -c "print(len(open('x.txt', encoding='utf-8').read().strip()))"`.

## Title (max 40 characters)

| # | Title | Characters | Why |
|---|---|---:|---|
| 1 | `Cigala: every choice grows a tree` | 33 | Recommended. Uses the team name and the portal's headline; memorable in the main ranking. |
| 2 | `Lumi: a financial twin for students` | 35 | Leads with the guide character and says exactly what it is (UBS wording: financial twin). |
| 3 | `Tree of Life: explore your money choices` | 40 | Most descriptive; uses all 40 characters. |

TODO (Juan): pick one. The README hero uses option 1; change it there too if you choose another.

## Short description (max 100 characters)

| # | Short description | Characters | Note |
|---|---|---:|---|
| 1 | `A financial twin for students: explore what each life choice does to your next 10 years. Verified.` | 98 | Recommended. |
| 2 | `Explore, don't predict: a verified financial twin that shows where each student life choice breaks.` | 99 | Echoes the UBS feedback. |
| 3 | `A cinematic tree of your financial future: each branch a decision, each number from a tested engine.` | 100 | Leads with the experience. |

## Long description (max 1000 characters): 949 characters

```text
Cigala is a financial twin for students, drawn as a tree of life. Roots are who you are: a questionnaire, voice, or a payslip photo, bank statement and lease read by a frugal multimodal chain (local OCR, a small model, arithmetic checks; a vision model only when a check fails). On 60 synthetic documents: 97.7% accuracy at 154x lower cost than a frontier model, and 73% of images never leave the device. Branches are decisions you explore: a deterministic monthly engine that reproduces the UBS starter kit exactly, with editable sourced assumptions, plan check, break-even, goal-seek, reverse stress tests, timing and four weather stress scenarios. Monte Carlo is only an optional lens. Six live validation checks pass and every number has a trace id. Lumi, the guide, explains in EN/ES/FR/DE by voice and never recommends; every number it says is checked against the engine. Free, so a student network could offer it before students sign a lease.
```

Every claim traces to the repo: the benchmark ([`multimodal/benchmark/RESULTS.md`](../../multimodal/benchmark/RESULTS.md)), the starter-kit reproduction and the six checks ([`core/validation.py`](../../core/validation.py)), exploration ([`core/README.md`](../../core/README.md)), and number grounding and the advice guard ([`api/README.md`](../../api/README.md)).

## Public link

`https://github.com/Jlopvs24/lauzhack-26-cigala`. The repo is **private** today; make it public only after the secret scan in [`checklist.md`](checklist.md).

## Challenges to tick

- [x] **UBS – AI Financial Twin** (main)
- [x] **AXA – Frugal use of Multimodal AI**
- [x] **IMC – Tech for Good**
- Main ranking: automatic, every project is in it.
- Do **not** tick Logitech, JetBrains, Nexthink, Scholé or SBB.

## Thumbnail brief (max 300 KB)

- **Content:** the photoreal tree at dawn from the web app's master still, with Lumi (the glowing guide orb) beside the trunk. One limb is lit (the chosen branch) and the others are greyed, as in the app. Optionally, a small overlay card in the app's style reads *"Plan check: Needs financing · month 7"* to hint that this is about money, not gardening.
- **Text on the image:** the title only (for example *"Cigala"* plus *"every choice grows a tree"*), large and legible at 300 px wide. No logos of UBS, AXA or IMC, and no fake UI numbers beyond the real month-7 hook.
- **Source:** a screenshot of the start portal or of the tree (`web/public/tree/`, master still). No new image generation is needed. Lumi's art is in `web/assets/character/guide/`.
- **Format:** 1280 × 720 (16:9) JPEG or WebP, quality around 75. Check the size is under 300 KB: `python -c "import os; print(os.path.getsize('thumb.jpg') // 1024, 'KB')"`. If it is too big, resize to 960 × 540 or lower the quality.
- **Save as:** `docs/submission/thumbnail.jpg` (commit it; it is also useful as the README hero).

## After submitting

- [ ] Invite the teammate (Lluc, `@llucliment`) to the project on the platform.
- [ ] Open the public link in a private window: the README renders, the screenshots load, and there are no 404s.
- [ ] Post the submission confirmation on the board.
