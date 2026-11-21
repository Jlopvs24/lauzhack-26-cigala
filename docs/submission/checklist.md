# Pre-submission checklist

Hard stop **Sun 22 Nov 12:00**. Feature freeze **Sun 09:00**: after that, only fixes and demo polish. Work top to bottom. Tick a box only after running the command, and write what you saw next to it.

## 0. Figures (after the last engine merge, again at 11:00)

```bash
python scripts/pitch_figures.py            # about 5 s: engine, demo path, personal condition, AXA, IMC
python scripts/pitch_figures.py --tests    # minutes: adds test pass counts
```

- [ ] Every engine figure in `README.md`, `docs/pitch.md`, `docs/submission/video.md` and the captions matches the script's output. The docs were last filled from it on Sat 21 Nov 20:50 (engine `core-1.1`). Update anything that moved.
- [ ] The README's test line matches `--tests`.
- [ ] Validation prints `6/6`.

## 1. Repository: before making it public (Sun 11:00–11:30)

**Secret scan.** Run all of these from the repo root in Git Bash. The commands print counts or file names only, never the matched values, so they are safe to paste on the board.

```bash
git fetch --all --prune

# a) Key patterns anywhere in history, all branches (expect 0)
git log -p --all | grep -cE 'sk-or-v1-[0-9a-f]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|tgp_v1_[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}'

# b) Generic "KEY=value" assignments in tracked files (expect nothing)
git grep -nE '(API_KEY|SECRET|TOKEN|PASSWORD)\s*[=:]\s*["'"'"']?[A-Za-z0-9_\-]{16,}' -- . ':!*.lock' ':!package-lock.json' | cut -d: -f1,2

# c) Files that must never be tracked (expect only .env.example)
git ls-files | grep -iE '(^|/)\.env|settings\.local\.json|^vendor/|ubs-kit|api/models/|\.onnx$|voices-.*\.bin$|usage\.jsonl$'

# d) Optional but stronger, if gitleaks is installed (expect "no leaks found")
gitleaks detect --source . --log-opts="--all" --redact
```

- [ ] (a) prints `0`. It printed `0` on Sat 21 Nov 18:55; re-run after the last merge.
- [ ] (b) prints nothing.
- [ ] (c) prints only `.env.example`.
- [ ] (d) passes, or record "gitleaks not installed".
- [ ] **If anything is found:** do not make the repo public. Revoke the key at the provider first (OpenRouter, Together), then remove it from history (`git filter-repo`, which needs the lead's approval because it is a force-push), and only then go public.

**Content and licensing:**

- [ ] No UBS kit files are tracked (check (c) above).
- [ ] `data/synthetic/` holds documents rendered from UBS synthetic profiles (invented names and IBANs; amounts from the kit). The lead decides whether they go public as they are. If UBS objects, remove `data/synthetic/docs` before flipping; anyone with kit access can regenerate them with `python -m multimodal.gen.generate`.
- [ ] License: the README states that there is no license file. Add one (for example MIT) only if the team decides to.
- [ ] README: screenshots exist in `docs/submission/screenshots/` (6 files, see the README table), the video link has been added, and the title matches the form.
- [ ] The only remaining TODOs are the product name, screenshots and video: `git grep -n "TODO (" -- README.md docs/pitch.md docs/submission/`.
- [ ] Every PR that should ship is merged into `master`, and `git log origin/master -1` is the commit you demo.

**Make it public** (lead only):

```bash
gh repo edit Jlopvs24/lauzhack-26-cigala --visibility public --accept-visibility-change-consequences
gh repo view Jlopvs24/lauzhack-26-cigala --json visibility -q .visibility    # expect PUBLIC
```

- [ ] Open the repo in a private window, logged out: the README renders and the mermaid diagram draws.

## 2. Demo laptop (Sun 11:00, then again at 12:15 before judging)

**Code and services:**

- [ ] On `master` at the commit you demo: `git status` is clean.
- [ ] API: `python -m uvicorn api.main:app --port 8000`. Then `curl -s http://127.0.0.1:8000/health` shows `"engine":"core"`, `"personal_conditions_supported":true`, `"llm":{"available":true…}`, Kokoro `available:true`, and an `llm_budget` with money remaining. The shared API on Sat 20:50 predated the budget guard: restart it on current `master`.
- [ ] `curl -s http://127.0.0.1:8000/validation` shows `"passed":6,"total":6`, and the header badge reads **Verified 6/6**.
- [ ] **Personal conditions work end to end:**
  ```bash
  curl -s -X POST http://127.0.0.1:8000/tree/personalize -H "Content-Type: application/json" \
    -d '{"path":["2"],"node_id":"2","text":"I would get a CHF 600/month scholarship during the master","language":"en"}'
  ```
  It must return a `proposal` with `monthly_net_income` `add` `600`, months `0`–`24`, and `numbers_not_in_your_words: []`. On Sat 20:45 it did: 2.5 s, USD 0.00008. Then do it in the UI: **Make it mine** is on the current branch (#67). After **Confirm**, the master's card must show the new gap, and the branch must be marked as yours.
- [ ] **Document extraction:** run this three times and expect HTTP 200 each time, at 10 s or less:
  ```bash
  curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" -X POST http://127.0.0.1:8000/profiles/extract -F "files=@data/synthetic/docs/P00001-payslip.jpg"
  ```
  On Sat 20:40 the shared API returned 200 twice, but took **57 s and 74 s** (the benchmark's median is 5.1 s). If it is still slow, skip the documents beat. At 18:52 the same route had failed with `TypeError: 'module' object is not callable`: `api/main.py` imports `extract` from `multimodal` at call time, and importing `multimodal.extract.profile` replaces that name with the subpackage. The code is unchanged since then, so make sure the third call also returns 200.
- [ ] Web: `cd web && npm run dev` serves `http://127.0.0.1:5175`. **Try the demo: Alexia** grows the tree, and the master's branch says *"cash runs short from month 7"*.
- [ ] Clear rehearsal conditions: open a new private window, or remove them under **Your conditions**.
- [ ] Click the whole demo path once so every node is cached, then reload.

**Kokoro TTS model files:**

- [ ] `api/models/voices-v1.0.bin` (27 MB) and `api/models/kokoro-v1.0.onnx` (fp32, 310 MB) exist, or `kokoro-v1.0.int8.onnx` (88 MB). If they are missing, run `python -m api.fetch_models --fp32`, which needs internet.
- [ ] `curl -s -X POST http://127.0.0.1:8000/voice/tts -H "Content-Type: application/json" -d '{"text":"Hello, I am Lumi.","language":"en"}' -o lumi.wav` gives a playable WAV. Repeat with `"language":"es"` and `"fr"`.

**Keys and budget:**

- [ ] `.env.local` exists at the repo root with `OPENROUTER_API_KEY` set. Check without printing the value: `grep -c '^OPENROUTER_API_KEY=.\+' .env.local` prints `1`.
- [ ] `LLM_DAILY_BUDGET_USD` (default 2.0) leaves room for judging day: rehearsals spend from the same daily budget. Raise it in `.env.local` if rehearsals have eaten it. When the budget is reached, Lumi and *Make it mine* fall back to templates.
- [ ] The OpenRouter credit covers the demo (check on openrouter.ai).

**Audio and microphone:**

- [ ] Speakers or HDMI audio are the Windows output, at about 70% volume. Lumi is audible at the back of the judging table.
- [ ] Microphone: the Chrome site permission for `127.0.0.1:5175` is **Allow**. Test **Speak** in *Make it mine* and dictation in the chat panel.
- [ ] Browser speech recognition in Chrome needs internet. Without it, type the condition; the proposal is the same.
- [ ] Notifications are off (Windows Focus), the laptop is charging, and sleep is disabled.

**Offline and degraded fallbacks:**

| What fails | What still works | What to do |
|---|---|---|
| No internet | Engine, tree, levers, report, *Verified*, Kokoro TTS | Lumi's answers use engine templates. **Make it mine needs the LLM**: without it, `/tree/personalize` answers with a clarifying question and no proposal, so play the climax from the backup video. Skip document extraction. Fonts fall back from Google Fonts. |
| OpenRouter out of credit, or the daily budget reached | Same as above | Same as above. Raise `LLM_DAILY_BUDGET_USD` before judging, not during. |
| Kokoro does not load | Browser `speechSynthesis` | Check a matching voice exists, or click **Sound off** and read the bubbles. |
| Microphone does not work | Typed chat and typed conditions | Type. |
| Web app crashes | API docs at `/docs` and `/validation` | Switch to the backup video. |
| Laptop dies | – | A second laptop with the repo, `npm ci` and models fetched; the video on a USB stick and online. |

## 3. Submission (Sun 11:30, before 12:00)

- [ ] Paste the fields from [`form.md`](form.md): title, short and long descriptions, public link, thumbnail (300 KB or less), and the challenges UBS, AXA and IMC.
- [ ] Invite the teammate on the platform.
- [ ] Post on the board: submitted, the link, and the commit that was demoed.
- [ ] Do not push to `master` after 12:00.
