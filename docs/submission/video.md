# Backup video: 2:00 shot list

> **The main demo is now a recorded video of about 4:20** (thread 0: screen recording with cursor, voice note, chat edit, weather, compare, path report, Verified, documents, Spanish), narrated live by the team in the 5-minute slot. This 2:00 cut is optional: a short version to link from the README.

Purpose: a recording of the real app, to play if the live demo fails at judging and to link from the README. Same story as [`docs/pitch.md`](../pitch.md), cut to two minutes, with *Make it mine* as the climax. Record by Sun 10:30 so there is time for one retake.

> Captions quote engine figures. Take them from `python scripts/pitch_figures.py` **on the commit you record**, and check them against what the app shows during the take.

## Recording setup

- **Screen:** Chrome full screen (F11) at 1920 × 1080, language EN, light mode, browser zoom 100%. Close notifications and other tabs.
- **Tool:** OBS Studio (Display Capture, 1080p, 30 fps, MP4) or the Windows Game Bar (Win + Alt + R). Record **system audio**, so Lumi's Kokoro voice is captured, plus a separate voice-over track if possible.
- **Before you record:** click through the whole path once, so every node is cached, then **reload**. A reload starts fresh (no chat, pins, personal conditions or Live consent) and lets Lumi narrate again.
- **Voice-over:** record it afterwards over the silent parts, never over Lumi. Put subtitles on Lumi's lines.
- **Output:** `arbor-demo.mp4`, under 2:00. Upload it as an **unlisted** YouTube video (or attach it to a GitHub release) and add the link to the README. TODO (team): paste the link here and in the README.

## Shots

| # | Time | Shot (what is on screen) | Audio | On-screen caption |
|---|---|---|---|---|
| 1 | 0:00–0:07 | Start portal: *"Every choice grows a different tree."* Slow push-in. | VO: "Alexia is 20, studies in Lausanne and has CHF 8,000 saved. Work, a master's, or move abroad?" | **Arbor**: explore your futures before you live them |
| 2 | 0:07–0:15 | **Try the demo: Alexia**: the camera rises from the roots to the whole tree. | Music | Roots from a questionnaire, voice or documents (AXA: 97.7% accuracy, 154× cheaper than a frontier model) |
| 3 | 0:15–0:32 | Click **Do a master's**: the camera flies in, the siblings grey out, and the card shows the plan check. | **Lumi** (full line): "Do a master's… Plan check: needs financing. In this scenario the cash runs short from month 7…" | UBS: same result as the UBS starter kit, reproduced exactly |
| 4 | 0:32–0:47 | **Report** → *What would have to be true*. | VO: "Not a forecast: what would have to be true, and what would fix it. The salary after the master's matters most, and no salary fixes month 7." | Break-even salary: *(figure from the script)* |
| 5 | 0:47–1:15 | **Make it mine** → speak *"I'd get a CHF 600 a month scholarship during the master's"* → **Check it** → proposal *+CHF 600/month, months 1–24* → **Apply to this branch** → **Confirm** → the branch re-grows. Hold on the master's card and the study-loan card changing. | VO: "She adds what the model can't know. Plain rules read her words, using only numbers she said. She confirms, and the branch re-grows." | Funding gap: *(before → after, from the script)* · Study loan: Needs financing → Holds |
| 6 | 1:15–1:35 | On the weather rail pick **Pessimistic** (cards recompute and say what the outlook does), **Reset to neutral**, then **Study loan of CHF 15,000** → **Repay over about 5 years** → **Open your report**: the brief, *her conditions*, *what would fix it*, *room to move*, the stress table. | VO: "Weather she doesn't choose, then her own report, with her condition, every result traceable, ready as a PDF." | No funding gap and goals met in 4 of 4 selected stress what-ifs *(check in the take)* |
| 7 | 1:35–1:45 | Click the **Verified 10/10** badge: the panel with ten passed checks. | VO: "Ten checks run live on the engine, four of them on her own branches." | 10/10 live checks (+4 on your own branches) |
| 8 | 1:45–1:53 | Lumi is docked at the bottom right; open the conversation and she moves into the chat panel. Ask by voice *"Why does the master's run short?"*. Lumi answers aloud, her mouth in sync, and *Session API cost* is visible. | **Lumi's** answer (cut the wait in editing; never edit the words) | Lumi explains, never recommends · open-weight model · local voice, cost 0 |
| 9 | 1:53–2:00 | Switch to **ES**: the tree with Lumi's bubble in Spanish. End card. | VO: "Free, four languages, built for students who can't afford an adviser. Arbor: explore your futures before you live them." | Arbor · UBS · AXA · IMC · github.com/Jlopvs24/lauzhack-26-cigala |

## Fallbacks while recording

- **If the parse asks a clarifying question,** keep it in the video and answer *"for the two years of the master's"*. It shows the parser never guesses.
- **If Lumi's answer in shot 8 takes more than 5 s,** cut the wait.
