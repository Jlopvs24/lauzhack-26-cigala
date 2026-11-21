# Pre-submission checklist

Hard stop **Sun 22 Nov 12:00**. Feature freeze **Sun 09:00**: after that, only fixes and demo polish. Work top to bottom. Tick a box only after running the command, and write what you saw next to it.

## 1. Repository: before making it public (Sun 11:00–11:30)

**Secret scan.** Run all of these from the repo root in Git Bash. The commands print counts or file names only, never the matched values, so they are safe to paste on the board.

```bash
git fetch --all --prune

# a) Key patterns anywhere in history, all branches (expect 0)
git log -p --all | grep -cE 'sk-or-v1-[0-9a-f]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|tgp_v1_[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}'

# b) Generic "KEY=value" assignments in tracked files (expect only .env.example with empty values)
git grep -nE '(API_KEY|SECRET|TOKEN|PASSWORD)\s*[=:]\s*["'"'"']?[A-Za-z0-9_\-]{16,}' -- . ':!*.lock' ':!package-lock.json' | cut -d: -f1,2

# c) Files that must never be tracked (expect only .env.example)
git ls-files | grep -iE '(^|/)\.env|settings\.local\.json|^vendor/|ubs-kit|api/models/|\.onnx$|voices-.*\.bin$|usage\.jsonl$'

# d) Optional but stronger, if gitleaks is installed (expect "no leaks found")
gitleaks detect --source . --log-opts="--all" --redact
```

- [ ] (a) prints `0`. It printed `0` on Sat 21 Nov 18:55 on this branch; re-run after the last merge.
- [ ] (b) prints nothing, or only `.env.example` lines with empty values.
- [ ] (c) prints only `.env.example`.
- [ ] (d) passes, or record "gitleaks not installed".
- [ ] **If anything is found:** do not make the repo public. Revoke the key at the provider first (OpenRouter, Together), then remove it from history (`git filter-repo`, which needs the lead's approval because it is a force-push), and only then go public.

**Content and licensing:**

- [ ] No UBS kit files are tracked (check (c) above), and `vendor/` is gitignored.
- [ ] **UBS-derived synthetic documents** (`data/synthetic/`, rendered from UBS synthetic profiles with invented names and IBANs): someone confirmed with UBS (Discord #2026-sponsor-ubs or their booth) that these may be public. If not, remove `data/synthetic/docs` from the public repo before flipping, and say in the README that `python -m multimodal.gen.generate` regenerates them for anyone with kit access.
- [ ] README: screenshots exist in `docs/submission/screenshots/` (6 files, see the README table), the video link has been added, and the title matches the form.
- [ ] Every `TODO (team)` and `TODO (Juan)` in `README.md`, `docs/pitch.md` and `docs/submission/*` is resolved or deliberately left: `git grep -n "TODO (" -- README.md docs/`.
- [ ] LICENSE: decide (for example MIT) and add the file, or remove the TODO line in the README.
- [ ] Every PR that should ship is merged into `master`, and `git log origin/master -1` is the commit you demo.

**Make it public** (lead only):

```bash
gh repo edit Jlopvs24/lauzhack-26-cigala --visibility public --accept-visibility-change-consequences
gh repo view Jlopvs24/lauzhack-26-cigala --json visibility -q .visibility    # expect PUBLIC
```

- [ ] Open the repo in a private window, logged out: the README renders and the mermaid diagram draws.

## 2. Demo laptop (Sun 11:00, then again at 12:15 before judging)

**Code and services:**

- [ ] On `master` at the commit you demo: `git status` is clean and `git log -1` matches.
- [ ] API: `python -m uvicorn api.main:app --port 8000` (or the shared command in `api/README.md`). Then `curl -s http://127.0.0.1:8000/health` shows `"engine":"core"`, `"llm":{"available":true…}` and `"kokoro":{"available":true…}`.
- [ ] `curl -s http://127.0.0.1:8000/validation` shows `"passed":6,"total":6`. On Sat 18:50 the running API returned 404 because it predated #41; restart it on current `master`.
- [ ] **Document extraction works twice in a row.** On Sat 18:52, `POST /profiles/extract` returned `502 extraction failed: TypeError: 'module' object is not callable`. Cause: once `multimodal.extract.profile` has been imported, `multimodal.extract` is the subpackage instead of the function, so every call after the first fails. Owner: thread 3, reported to thread 0. After the fix, run this twice and expect HTTP 200 both times:
  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/profiles/extract \
    -F "files=@data/synthetic/docs/P00001-payslip.jpg" -F "files=@data/synthetic/docs/P00001-bank_statement.pdf" \
    -F "files=@data/synthetic/docs/P00001-rental_contract.jpg"
  ```
- [ ] Web: `cd web && npm run dev` serves `http://127.0.0.1:5175`. The portal loads, **Try the demo: Alexia** grows the tree, and the master's branch says *"cash runs short from month 7"*.
- [ ] Click the whole demo path once (`2` → `2.2` → back → `2.3` → `2.3.1` → report) so every node is cached, then reload the page.

**Kokoro TTS model files:**

- [ ] `api/models/voices-v1.0.bin` (27 MB) and `api/models/kokoro-v1.0.onnx` (fp32, 310 MB) exist, or `kokoro-v1.0.int8.onnx` (88 MB). If they are missing, run `python -m api.fetch_models --fp32`, which needs internet: do it before the venue Wi-Fi gets busy.
- [ ] `curl -s -X POST http://127.0.0.1:8000/voice/tts -H "Content-Type: application/json" -d '{"text":"Hello, I am Lumi.","language":"en"}' -o lumi.wav` gives a playable WAV. Repeat with `"language":"es"`.

**Keys:**

- [ ] `.env.local` exists at the repo root with `OPENROUTER_API_KEY` set. Check without printing the value: `grep -c '^OPENROUTER_API_KEY=.\+' .env.local` prints `1`.
- [ ] The OpenRouter balance covers the demo. The benchmark used USD 2.14 and the imagery USD 2.30; check the remaining credit on openrouter.ai.

**Audio and microphone:**

- [ ] Speakers or HDMI audio are selected as the Windows output, at about 70% volume. Lumi is audible at the back of the judging table.
- [ ] Microphone: Chrome site permission for `127.0.0.1:5175` and `127.0.0.1:8000` is set to **Allow** (padlock → Site settings). Test a dictation in the chat panel.
- [ ] Browser speech recognition in Chrome uses Google's servers and needs internet. Without it, type in the chat panel or send a recorded voice note (server STT through OpenRouter).
- [ ] Notifications are off (Windows Focus), the laptop is charging, and sleep is disabled for the session.

**Offline and degraded fallbacks** (know them before you need them):

| What fails | What still works | What to do |
|---|---|---|
| No internet | Engine, tree, levers, report, validation, Kokoro TTS (local) | Lumi's chat answers fall back to engine templates. Skip document extraction: use **Try the demo: Alexia**. Fonts come from Google Fonts, so the UI uses fallback fonts; acceptable. |
| OpenRouter key out of credit or invalid | Same as above | Same as above. Do not top up during judging; the demo does not need it. |
| Kokoro does not load | Browser `speechSynthesis` (the app switches automatically) | Check that a matching voice exists for the language, or click **Sound off** and read the bubbles. |
| Microphone does not work | Typed chat | Type the question. |
| Web app crashes | API docs at `http://127.0.0.1:8000/docs` and `/validation` | Switch to the backup video (`docs/submission/video.md`). |
| Laptop dies | – | A second laptop with the repo cloned, `npm ci` and models fetched, plus the backup video on a USB stick and online. |

## 3. Submission (Sun 11:30, before 12:00)

- [ ] Paste the fields from [`form.md`](form.md): title, short and long descriptions, public link, thumbnail (300 KB or less), and the challenges UBS, AXA and IMC.
- [ ] Invite the teammate on the platform.
- [ ] Post on the board: submitted, the link, and the commit that was demoed.
- [ ] Do not push to `master` after 12:00.
