# Track B: cinematic photoreal tree (prototype)

Standalone page, not wired into `web/src` yet. Owner: Juan's Claude thread 6.

```bash
# uses the shared API on :8000 (override with ?api=)
cd web && python -m http.server 5175 --bind 127.0.0.1
# open http://127.0.0.1:5175/prototypes/cinematic/   (?api=http://host:port to change the API)
```

## How it works

- **13 matched stills** (`img/*.webp`, 2.7 MB): one master photo of the tree, then close-ups of
  the roots, the 3 limbs and 3 sub-branches per limb. Each close-up was generated (OpenRouter,
  `google/gemini-3.1-flash-image`) from an **exact crop of its parent**, then colour-matched, so it
  sits on a known rectangle of the master's pixel space (`img/stills.json`).
- **Camera**: flies between rectangles (zoom interpolated in log space, GSAP); the sharper still
  fades in on arrival over the matched crop, so the zoom looks continuous. Slow breathing + bounded
  pointer parallax (free look is limited to the current node). Back / Esc / scroll-up = one level.
- **Grey branches**: `img/*.lab.png` label maps (limb*10 + sub-branch) per still. Siblings and
  pruned branches (API `status: "pruned"`, or nodes already seen on the client) are desaturated
  with a feathered mask. Pruned labels show the name only and are not clickable.
- **Data**: live `POST /tree/expand`. Node `k` maps to limb k (1 left, 2 centre, 3 right),
  `k.i` to its sub-branch i; depth 3 zooms further into the depth-2 still (no extra image).
- **Lumi** (`web/assets/character/guide`) narrates every node from engine numbers (no LLM) and
  reads it aloud automatically after the first click: `/voice/tts`, browser `speechSynthesis` as
  fallback. Mute toggle, off by default. Report panel, chat to `/agent/ask`, mic = browser STT.

## Shell (plan "Product shell")

- **Start portal** on the roots still: one line of value, then *Try the demo: Alexia* (straight up
  to the tree) or *Start with your own roots*: text, documents (PDF/JPG/PNG) and voice dictation →
  `POST /profiles/extract` → quick editable review (age, savings, income, rent, other costs) →
  the tree grows from that profile (`profile` is sent with every `/tree/expand` and `/agent/ask`).
  The full questionnaire/provenance flow is Lluc's `Roots.jsx`; this panel is the cinematic stand-in.
- **Language** EN / ES / FR / DE (`i18n.js`): UI, Lumi's narration, report, and `context.language`
  for the agent. Engine node texts of the Alexia tree are translated client-side; unknown engine text
  stays on screen but is never spoken in another language's voice.
- **Voice matches the language**: server Kokoro (`/voice/tts`) only for languages `/health` lists
  (en, es, fr, it, pt); otherwise a browser voice whose `lang` matches; otherwise Lumi stays silent
  and says so. Kokoro model files: `python -m api.fetch_models` (gitignored `api/models/`).
- **Light / dark**: dawn photo by day; at night the scene itself is graded to dusk (world filter,
  navy multiply grade, moon glow, thinner mist) with a 1.4 s cross-fade. Default = system setting.

## Regenerate

`pipeline/gen.py` (one image call), `pipeline/build.py` (colour-match, label maps, webp),
prompts and `pipeline/costs.log` (13 calls, USD 0.88 total).
