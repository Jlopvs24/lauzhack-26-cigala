# Arbor — pitch script (5 min + 5 min Q&A)

Video: `arbor-demo-v2.mp4` (4:50, 1080p). It runs the whole 5 minutes; you narrate over it.
Two voices: **J** = Juan (story, product), **L** = Lluc (engine, maths, validation).
Press play as you say the first line. Only two moments have sound: Lumi speaking (0:14–0:28) and the voice note (1:25–1:30). **Stay quiet during both.**
Lines are written for a calm pace (~130 words/min). If you fall behind, skip the lines marked *(optional)*.

---

### 0:00–0:14 · Portal: the hook
**J:** Meet Alexia. She's 20, studies in Lausanne and has 8,000 francs saved. She has to choose: start working, do a master's, or move abroad. A financial advisor costs more than she can afford, and a chatbot will happily invent numbers. So we built **Arbor: explore your futures before you live them.**

### 0:14–0:28 · Tree grows: Lumi speaks
*(Silence: Lumi reads her first message aloud.)*

### 0:28–0:42 · Three options on the tree
**J:** Each branch is one decision. The cards are in plain words, two lines each, and they compare against each other. Lumi, our guide, explains. She never recommends.

### 0:42–0:58 · Master's branch
**J:** Alexia opens the master's. The tree zooms in and grows its own options.
**L:** And here is the first hard truth: on a student job only, the money runs out in **month 7** unless she borrows about **18,600 francs**. That number comes from a deterministic engine, never from the AI. It's Swiss: official 2026 tax rates by city, real social contributions, pillar 3a.

### 0:58–1:22 · Branch report: what would have to be true
**L:** We don't predict the future. We ask *what would have to be true*: which salary makes the master's pay off, what monthly change closes the gap, what breaks the plan first. Each assumption has a "try" button, so you can push it and see.

### 1:22–1:32 · Voice note
**J:** But Alexia knows something the model doesn't. So she just tells Lumi.
*(Silence: "What if I get a scholarship of 600 francs a month?")*

### 1:32–1:56 · A new branch grows
**J:** Lumi understands it, the engine computes it, and a new branch grows on the tree: **"Your branch."** The money now lasts until **month 13**, and the gap drops from 18,600 to about **3,900**.
**L:** The AI only turns her words into a structured change. Every number is recomputed by the engine and then checked, and Lumi's sentence is written from those checked numbers.

### 1:56–2:08 · Typed edit
**J:** She can also edit by typing. "Make it 800 instead." The same branch updates, and now **the cash never runs out.**

### 2:08–2:34 · Weather: what she doesn't choose
**L:** On the left is the weather: what you don't choose. Pessimistic means higher prices, slower pay growth and weaker markets. Every card recomputes, about **24,000 francs** less in ten years, and only **1 of 4** options still holds. You can add single factors too, like a weak job market. These are named "what-if" worlds, not probabilities.

### 2:34–3:11 · Compare
**J:** Instead of comparing in your head, tap "+" on up to four paths and see them side by side: one chart, one column per path, highest and lowest values marked, never "best". "Show only differences" keeps just what changes.

### 3:11–3:46 · Path report
**J:** At the end of a branch, a one-page path report: the headline in "if… then…" language, the plan check, money over time, what would fix it, and the stress tests. *(optional)* It saves as a PDF.

### 3:46–3:57 · Verified 10/10
**L:** And how do you know it's right? Ten checks run live on the engine: accounting identities on all 40 nodes with zero error, reproducibility, monotonicity, branch isolation, the UBS starter kit reproduced exactly, and four more on the branches the user creates.

### 3:57–4:28 · Your own documents (AXA)
**J:** You don't have to type your life in. Drop a payslip, a rental contract and a bank statement, and the form fills itself, with the **source and confidence of every field**.
**L:** That's our frugal pipeline: local OCR and a small open model, not a frontier model for everything. On our benchmark it reaches **97.7% accuracy against 99.4%, at 154 times lower cost**, and only about a quarter of the images ever leave the device. The model is open-weight, so a bank can host it.

### 4:28–4:50 · Spanish: the close (IMC)
**J:** And it's free, in four languages, with a voice that matches. A volunteer at the Erasmus Student Network could sit next to a student before they sign their first lease. Most students can't afford a financial advisor. Arbor lets them **explore their futures before they live them.** Thank you.

---

## Q&A cheat sheet (5 min)

| Likely question | Short answer |
|---|---|
| Is the AI doing the maths? | No. A deterministic Python engine computes every number (120 months, Swiss tax, AHV/ALV, BVG, 3a). The LLM only turns words into structured changes and words the explanation, using numbers checked against the engine. |
| Isn't this a forecast? | No, it's exploration. Each branch is "if this, then that" under visible assumptions. Monte Carlo exists only as an optional uncertainty lens, off by default. |
| How did you validate it? | Verified panel, 10 live checks: accounting identities on all 40 nodes (max error CHF 0.00), same inputs give the same trace, monotonicity (more tuition never raises cash), branch isolation, UBS starter kit reproduced exactly, and 4 checks on user-created branches. Plus unit tests. |
| Where do the assumptions come from? | UBS kit profiles for Alexia, ESTV 2026 tax by city and household, Swiss social contribution rates, public salary and rent data, each cited. Parameters calibrated against public Swiss targets (core/bench). |
| What if Lumi misunderstands? | She only maps words to the node's own levers, uses the user's numbers (never invented ones), asks one clarifying question when unsure, and every change can be undone. |
| Privacy? | No storage: a reload starts fresh. Open-weight model (Qwen, Apache-2.0) that a bank or NGO can self-host. Voice runs locally (Kokoro). Live calls are opt-in with consent. |
| Why not just GPT on everything (AXA)? | Measured: 97.7% vs 99.4% at 154× lower cost, faster, ~27% of images leave the device. Structured JSON goes into the engine, so it's auditable. |
| Cost to run? | Cents per session; we cap spending at $2/day. The engine is local and answers in ~30 ms. |
| Who is it for (IMC)? | Students and first-generation students who can't pay an advisor. Free, voice-first, 4 languages, and deployable by a non-profit like ESN. |
| What's next? | More life decisions (housing, Erasmus exchanges, first job offers), partner NGO pilots, self-hosted deployment. |
| Is it live or a video? | The video is the same app on this laptop. We can show it live right after, including a Lumi Live voice call. |

**After the pitch, at the booths:** run it live on the laptop (`127.0.0.1:5175`). Lumi Live (the realtime call) only if the wifi is good.
