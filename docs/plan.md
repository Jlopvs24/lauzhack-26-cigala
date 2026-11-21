# Plan — team cigala @ LauzHack 2026

Status: living document, owned by the coordination thread. Decisions marked **DECIDED** are fixed; **OPEN** ones must not be assumed.

## One project, three challenges

One submission (LauzHack allows one project per team), opting into:

| Challenge | What judges must understand we add |
|---|---|
| **UBS – AI Financial Twin** (main) | *Reliability*: every number comes from a deterministic, tested engine, never from the LLM. Explicit, editable assumptions with sources; uncertainty bands (Monte Carlo); sensitivity ("which assumption matters most"); calculation traces; accounting checks. |
| **AXA – Frugal multimodal AI** | *Why not just send everything to a frontier model*: our pipeline (browser STT / OCR / small extraction model → structured JSON → engine; LLM only narrates) is cheaper, faster, more private and auditable. Proven with a **measured benchmark** on synthetic documents with known ground truth (accuracy, cost, latency vs. a big model). Cost per session visible in the UI. |
| **IMC – Tech for Good** | *Social impact*: people who most need a financial advisor (students, first-gen, exchange/Erasmus students) can't afford one. Free, voice-first, multilingual, deployable by a non-profit (e.g. Erasmus Student Network). |

UBS judging (draft): modelling correctness 25 · scenario/counterfactual exploration 20 · technical execution & validation 15 · UX 15 · innovation 15 · responsible design/transparency 10. LLM use earns nothing by itself.

## The product: a tree of life (DECIDED)

- **Roots = who you are today.** Filled by a short questionnaire *or* multimodal input: synthetic documents (payslip, bank statement, rental contract) via OCR/extraction, voice, text.
- **Trunk = current state**, with a transparent financial-health indicator (liquidity months, debt ratio, goal feasibility). Tree and character look healthier/weaker accordingly.
- **Branches = decisions.** **Lazy expansion with pruning**: at step 0 we simulate options 1, 2, 3, explain them, the user picks one. Picking 1 shows 1.1, 1.2, 1.3 and explains what decision 1 changed. Picking 1.1 prunes 2 and 3 (more than one level away). The user can always go **back one level** and switch. Only the current path, the siblings (shown greyed out for comparison) and the children exist: never thousands of nodes.
- **Weather = things you don't choose** (recession, inflation, market drawdown, job loss), toggled as stress on a node.
- **Leaf = the explanation**: metrics, comparison with sibling branches, charts, Monte Carlo bands, the key assumption, and the character walking across the screen explaining it.
- **Monte Carlo is per visible node** (e.g. 1,000 paths × 120 months, fixed seed). It gives uncertainty, it is not a forecast. Pruning bounds the number of nodes; Monte Carlo is the uncertainty inside each node.
- **Editable assumptions** from any node; the visible tree recomputes.

## The character (DECIDED, design OPEN)

An original little tree/sprout character, friendly and simple. It **never recommends or decides**: it explains possibilities and trade-offs so the user decides. Talks by text and audio; the user can type, send voice notes, or call it (conversational mode). Must be an original design (own silhouette, proportions, palette, name) — not a copy of any existing franchise character.

## Frontend experience (DECIDED 14:15, iterate until perfect)

- The screen IS a tree. Once the roots/trunk are defined, the options appear as real branches growing from the trunk.
- Choosing an option **zooms the camera into that branch**; its sub-options grow from it. Going back **zooms out** to the parent. Siblings stay visible but greyed. Smooth, physical, interruptible motion.
- The leaf opens the report (metrics, sibling comparison, bands, assumptions, checks).
- Design bar: "perfect", not a generic dashboard. Use the design skills (impeccable, emil-design-eng/animate/choreograph, taste-skill).

## Voice and conversation (DECIDED 14:15)

- The character shows its explanation in a **speech bubble** and in the **report**, and **reads its bubble aloud** at the same time (TTS).
- The user can talk back three ways: **type** in a chat, **record and send a voice note** (mic), or **call** the character (realtime conversational model, interruptible).
- Numbers always come from the engine; the character never recommends.

## Navigation and narration rules (DECIDED 15:00)

- **Lumi reads aloud automatically.** Every new bubble is spoken without any button (the first user gesture, e.g. choosing a branch, unlocks browser audio). A mute toggle exists but is off by default.
- **Free look is bounded.** The user may look around the current area, but cannot jump far: from level 4 you cannot fly to the roots. Navigation is one level back at a time (Back), plus free look around the current node.
- **Past branches stay drawn in grey.** Branches pruned earlier (siblings of every ancestor) keep their geometry visible, greyed out, with their name only. They are not simulated and not clickable. The API returns them as `status: "pruned"` nodes with label only (no `result`).

## Product shell (DECIDED 15:20)

- **Start portal** before the tree: short cinematic intro, then "Start with your own roots" (questionnaire / documents / voice) or "Try the demo: Alexia" (known roots, straight to the tree).
- **Language switch** EN (default) / ES / FR / DE for UI, Lumi's bubbles and the agent. **The voice must match the language** (never English text with a Spanish voice).
- **Light / dark mode** toggle (default: system), the scene itself adapts, not only the UI.

## UBS feedback at their booth (16:45) and the engine reframe (DECIDED)

UBS liked the idea. Their objection: **Monte Carlo as the engine is too easy and it predicts.** They want to **explore possibilities, not predict**. Monte Carlo may stay as an optional extra, not the core.

The core idea is to **SIMULATE and EXPLORE** possible futures, not to predict one. Lluc owns the math and decides how; the points below are suggestions, not a spec.

Suggestions for the engine (owner: Lluc, issue #21):
- The core is **deterministic, explicit scenario exploration**: each branch is a fully specified "if this, then that" world, with every assumption visible and editable.
- **Levers / what-ifs** on every node: change an assumption and see the whole visible tree recompute.
- **"What would have to be true"** analyses instead of forecasts: break-even (what salary makes the master's pay off, and by when), goal-seeking (what savings rate reaches the goal), reverse stress test (what breaks this plan first), and timing / path dependence (same decision one or two years later).
- **Stress scenarios** (the "weather") as named, deterministic what-ifs, not probabilities.
- **Monte Carlo** only as an optional "uncertainty lens", off by default, never shown as a forecast.
- Language everywhere (UI, Lumi, agent): "if… then…", "under these assumptions", never "you will" or "expected".

Frontend: **track B (cinematic AI imagery) chosen** at 16:45; track A stopped.

## Personal conditions → the tree re-grows (DECIDED 20:05, the core value-add)

The user can attach their OWN conditions to any branch, in words or voice, and the engine recomputes that branch and everything below it. Example: on "Do a master's" the user says "I'd get a CHF 600/month scholarship" or "I'd combine it with a 40% job": the master's card and all its children update, and new possibilities appear.

- **Two modes**: (a) *condition* = patch the chosen node (its subtree inherits it, cards recompute); (b) *new branch* = add a custom sibling ("Master's with scholarship") to compare against the original.
- **Flow**: chat/voice/text → `POST /tree/personalize` (LLM parses into the intervention schema using only the node's levers/assumptions; numbers come from the user, never invented; validation + ranges; asks one clarifying question if needed) → proposal chip the user confirms → `POST /tree/expand` with `custom_nodes` / `node_patches` → branch re-grows, custom items marked, siblings re-compared, report and Lumi include the conditions. Session-persisted.
- **Ownership**: core support for `custom_nodes` / `node_patches` (thread 1, with Lluc's OK since he owns core/) · `/tree/personalize` + agent tool (thread 2) · proposal/confirm UI component in `web/src/personalize/` (thread 7) mounted by the scene (thread 6).

## Comparing options (DECIDED 21:00, user feedback)

Feedback: "Do I enter one option, then another, and compare in my head? Where is the impact of each option on its own?"
- **Comparative cards**: the option cards at a node compare against each other (position on a shared scale for the headline metric, delta chips vs the other options, plan-check colour), not stand-alone numbers.
- **Impact alone**: each option shows what its own decision changes vs its parent and vs today.
- **"+ Add to comparison" (spec-sheet comparator)**: from any card or final report, add up to 4 paths to a compare bar; the comparison page shows one column per path, rows grouped by outcome / what would have to be true / stress / differing assumptions / your conditions, highest/lowest highlighted (never "best"), "show only differences", overlay chart. Data: `POST /tree/compare`.
- Ownership: UI in `web/src/compare/` (thread 10), API (thread 2), mounts in the scene (thread 6) and report header (thread 7).

## Demo persona (DECIDED)

**Alexia** (UBS kit): fictional 20-year-old student in Lausanne, CHF 8,000 savings, choosing between start working / master's / move abroad. Represents any student. The UBS starter kit already shows the master's path runs out of cash in month 7 — a good hook.

## Data rules (DECIDED)

- UBS kit is "all rights reserved": fetch with `bash scripts/fetch_ubs_kit.sh` into `vendor/ubs-kit` (gitignored). Never commit its files.
- We generate our own synthetic documents from UBS synthetic profiles (ground truth known) → roots input + AXA benchmark.
- Public data for assumptions (cost of living, tuition, salaries) must be cited with source and date.

## OPEN

- Exact questionnaire questions and decision tree content (next discussion).
- Realtime call provider (thread 2 researching).
- Character design and name.
- Demo script and pitch (Sunday morning).

## Timeline

| When | Milestone |
|---|---|
| Sat 15:00 | Contracts v1 agreed (`docs/contracts.md`) |
| Sat 20:00 | Thin end-to-end slice with Alexia: roots → 3 options → pick → children → leaf |
| Night | Multimodal roots + benchmark, agent + voice, weather, character animation |
| Sun 09:00 | Feature freeze: only fixes and polish |
| Sun 11:30 | Repo public, README, video, submission form |
| Sun 12:00 | Hard stop |

## Threads (Juan's side)

| Thread | Scope |
|---|---|
| 0 Coordination | plan, contracts, issues, board with Lluc, PR review |
| 1 Engine | `core/` |
| 2 API & agent | `api/` |
| 3 Multimodal roots & AXA benchmark | `multimodal/`, `data/synthetic/` |
| 4 Character & art | `web/assets/character/` |
| Lluc (Codex) | `web/` — tree UI and experience |
