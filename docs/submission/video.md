# Backup video: 2:00 shot list

Purpose: a recording of the real app, to play if the live demo fails at judging and to link from the README. Same story and numbers as [`docs/pitch.md`](../pitch.md), cut to two minutes. Record by Sun 10:30 so there is time for one retake.

## Recording setup

- **Screen:** Chrome full screen (F11) at 1920 × 1080, language EN, light mode (it reads better on projectors), browser zoom 100%. Close notifications and other tabs.
- **Tool:** OBS Studio (Display Capture, 1080p, 30 fps, MP4) or the Windows Game Bar (Win + Alt + R). Record **system audio**, so Lumi's Kokoro voice is captured, plus a separate voice-over track if possible.
- **Before you record:** click through the whole path once, so every node is cached and appears instantly. Then reload the page so Lumi narrates again: she does not repeat a bubble she already spoke in the same session.
- **Voice-over:** record it afterwards over the silent parts, not over Lumi. Put subtitles on Lumi's lines, because judges may watch without sound.
- **Output:** `cigala-demo.mp4`, under 2:00. Upload as an **unlisted** YouTube video (or attach it to a GitHub release) and add the link to the README. TODO (team): paste the link here and in the README.

## Shots

| # | Time | Shot (what is on screen) | Audio | On-screen caption |
|---|---|---|---|---|
| 1 | 0:00–0:08 | Start portal: *"Every choice grows a different tree."* Slow push-in. | VO: "Alexia is 20, studies in Lausanne and has CHF 8,000 saved. Work, a master's, or move abroad?" | **Cigala**: a financial twin for students |
| 2 | 0:08–0:28 | **Start with your own roots** → add the three `P00001-*` documents → **Read my roots** → the review screen. Zoom on one field's *Source · extraction confidence*. | VO: "Her payslip photo, bank statement and lease are read on the laptop: local OCR, a small model and arithmetic checks. A vision model only when a check fails." | AXA · 97.7% accuracy · 154× cheaper than a frontier model · 73% of images stay on the device |
| 3 | 0:28–0:33 | **Grow my tree**: the camera rises from the roots to the whole tree. | Music or silence | – |
| 4 | 0:33–0:50 | Click **Do a master's**: the camera flies into the limb, and the siblings grey out. | **Lumi** (full line): "Do a master's… Plan check: needs financing. In this scenario the cash runs short from month 7…" | UBS · same result as the UBS starter kit, reproduced exactly |
| 5 | 0:50–1:08 | **Report** → *What would have to be true*: levers, break-even, timing; plan check "Holds in 0 of 4 stress scenarios". | VO: "Not a prediction: what would have to be true. Salary after the master's matters most. Break-even against working is CHF 4,845 a month, and waiting a year costs 18,789." | Deterministic · every assumption sourced and editable |
| 6 | 1:08–1:25 | **Esc** → **Study loan of CHF 15,000** (card: *Funding gap CHF 3,820 from month 20*) → **Esc** → **Part-time master's with a 60% job**. | VO: "A loan shrinks the gap but doesn't close it. Part-time with a 60% job holds, in all four stress scenarios." | A funding gap is never hidden behind a score |
| 7 | 1:25–1:42 | **Employer pays the tuition** → **Open your report**: scroll *Stress scenarios* → *Validation and reproducibility*. Cut to the validation panel (or `/validation`): **6/6**. | VO: "Every number has a trace id. Six live checks pass: accounting identities on all 40 nodes, reproducibility, monotonicity, isolation, the UBS kit, verified thresholds." | 6/6 live checks |
| 8 | 1:42–1:52 | Open the conversation and ask by voice *"Why does the master's run short?"*. Lumi answers aloud; *Session API cost* is visible. | **Lumi's** answer (shorten it in the edit if needed) | Lumi explains and never recommends · every number checked against the engine |
| 9 | 1:52–2:00 | Switch to **ES**: the tree with Lumi's bubble in Spanish. End card. | VO: "Free, four languages, built for students who can't afford an adviser. Explore, don't predict." | Cigala · UBS · AXA · IMC · github.com/Jlopvs24/lauzhack-26-cigala |

## Fallbacks while recording

- If extraction fails (see [`checklist.md`](checklist.md)), record shot 2 as a pan over the benchmark table in `multimodal/benchmark/RESULTS.md`, then start the tree from **Try the demo: Alexia**.
- If Lumi's live answer in shot 8 takes more than 5 s, cut the wait in editing; never edit the answer's words.
- Every number in the captions must match what the app shows during the take. If the engine changed, re-check them with the commands at the end of `docs/pitch.md`.
