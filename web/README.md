# cigala web

The tree of life as a cinematic, photoreal scene. React + Vite + GSAP; every financial number comes from the API.
Requires Node 22.12+ or 24 and the backend from this repository (one shared API on port 8000).

```sh
cd web
npm ci
npm run dev        # http://127.0.0.1:5175, /api/* is proxied to 127.0.0.1:8000
npm test
npm run build
```

For a separately hosted API set `VITE_API_BASE_URL` (and `VITE_CALL_URL` for the live call page) in `web/.env.local` before building. No keys belong in Vite variables.

## What the user sees

1. **Start portal** on a close-up of the roots: *Try the demo: Alexia*, or *Start with your own roots* (Lluc's Roots flow: questionnaire, documents, dictation → `/profiles/extract` → review with provenance → apply).
2. The camera rises to the whole tree. Each option is a real limb with a label (health score, month cash runs short). Choosing one flies the camera into it; its children appear on the sub-limbs. Siblings and branches pruned earlier stay **greyed in the photo**, name only. Back / Esc / scroll-up = one level, never further; free look is bounded to the current node.
3. **Lumi** (`assets/character/guide`) explains every node from engine numbers and reads it aloud automatically after the first click. A node already narrated is never re-read: revisits say only "Back at …". Mute toggle, off by default.
4. **Report**: deterministic scenario first (10-year net worth, lowest cash, month cash runs short, month-by-month chart), comparison with sibling options, *what would have to be true* (the engine's `exploration` block, else sensitivity), goals, Lluc's assumption editor. Monte Carlo is the **uncertainty lens**, off by default; switching it on re-requests the node with `uncertainty: true` and is worded as "under these assumptions", never as a forecast.
5. **Conversation**: Lluc's chat (typed questions, dictation, recorded or uploaded voice notes → `/agent/ask`, `/voice/ask`), answers read by Lumi, and a link to the live call page (`/call` on the API).
6. **EN / ES / FR / DE** for UI, narration, report and `context.language`. The voice always matches the language: Kokoro (`/voice/tts`) for the languages `/health` lists, otherwise a matching browser voice, otherwise silence.
7. **Light / dark** (default: system). At night the photo itself is graded to dusk.

## Code

- `src/main.jsx`: the React shell (portal, header, drawers, state, API calls).
- `src/scene/scene.js`: stills, camera, greying, labels (framework-free). `geometry.js`: pure world/slot maths.
- `src/scene/narration.js`, `voice.js`, `report.js`, `i18n.js`.
- Lluc's logic kept as is: `Roots.jsx`, `Chat.jsx`, `Dictation.jsx`, `VoiceNote.jsx`, `api.js`, `profile.js`, `tree.js` (now accepts pruned nodes and exploration-first results), `results.js`, `NodeDetail.jsx` (its `Assumptions` editor is used in the report).

## Imagery

`public/tree/`: 14 matched 2752x1536 AVIF stills (6 MB): the master photo, the roots, the 3 limbs and 3 sub-limbs per limb. Each was generated from an exact crop of its parent, so it sits on a known rectangle of the master (`stills.json`) and the zoom crossfades without a seam. `stills.json` has a slot for every decision node down to level 4; a `null` slot zooms into the deepest ancestor still. `*.lab.png` label maps (limb*10 + sub-branch) drive the greying. Stills load lazily (current path, next level prefetched) and are freed after use. How to regenerate: `tree-pipeline/README.md`.
