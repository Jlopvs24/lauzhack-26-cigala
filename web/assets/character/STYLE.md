# Visual style: tree of life + character

Owner: Juan's Claude thread 4 (`web/assets/character/`). Guide for the web app (`web/`, Lluc).
Status: **proposal**. Character: Lumi, in `guide/` (open `guide/demo.html`).

## 1. Principles

- **Flat, rounded, friendly.** Simple shapes, soft curves, no gradients except very subtle ones on the sky; only the guide glows. No realistic bark or textures.
- **One outline for the tree:** `#2B2620`, 4px at 200px height (scale proportionally), `stroke-linecap: round; stroke-linejoin: round`. The guide (Lumi) has no outline on purpose: it glows.
- **Health is shown, not told:** colour and posture of leaves (and the character's colour and shape) change with financial health; the number is always also shown as text (accessibility, transparency).
- **The character never points at an option as "the best".** When it points, it points at the leaf/panel it is explaining, never a branch by itself.

## 2. Palette

| Token | Hex | Use |
|---|---|---|
| `--ink` | `#2B2620` | outlines, text |
| `--paper` | `#F6F3EA` | app background (day) |
| `--card` | `#FFFDF7` | leaf panels, cards |
| `--leaf-healthy` / `--leaf-healthy-dark` | `#5DBB63` / `#3E8E4A` | foliage, health "healthy" |
| `--leaf-fair` / `--leaf-fair-dark` | `#B9C24F` / `#8C9632` | health "fair" |
| `--leaf-weak` / `--leaf-weak-dark` | `#C9A26B` / `#94703F` | health "weak" |
| `--wood` | `#A9764E` | trunk, branches (healthy) |
| `--wood-weak` | `#9C7E64` | trunk when weak |
| `--soil` | `#6B4A35` | ground line, roots |
| `--root-light` | `#C89B74` | roots fill |
| `--fruit` | `#F2B33D` | fruits = savings / buffer; highlights |
| `--sky-calm` | `#DCEFF5` | weather: calm |
| `--sky-storm` | `#8C9AA6` | weather: stress scenario |
| `--rain` | `#5B8FB9` | rain drops |
| `--alert` | `#D9634C` | only for hard warnings (e.g. cash < 0) — never on a branch to discourage it |
| `--ghost` | `#C9CCC5` | branches not chosen |

Health mapping (same for tree and character): use the engine's health score, thresholds from `docs/contracts.md`.

```css
:root{
  --ink:#2B2620; --paper:#F6F3EA; --card:#FFFDF7;
  --leaf-healthy:#5DBB63; --leaf-healthy-dark:#3E8E4A;
  --leaf-fair:#B9C24F;    --leaf-fair-dark:#8C9632;
  --leaf-weak:#C9A26B;    --leaf-weak-dark:#94703F;
  --wood:#A9764E; --wood-weak:#9C7E64; --soil:#6B4A35; --root-light:#C89B74;
  --fruit:#F2B33D; --sky-calm:#DCEFF5; --sky-storm:#8C9AA6; --rain:#5B8FB9;
  --alert:#D9634C; --ghost:#C9CCC5;
}
```

## 3. Tree parts

**Roots (who you are).** Below a soft ground line (`--soil`, 4px). 3–6 roots as thick rounded tapering paths, fill `--root-light`, outline `--ink`. Each root ends in a small round "tag" (circle 10px) with an icon: payslip, bank, home, voice. A root filled from a document gets a tiny `--fruit` dot; a root with missing data is dashed (`stroke-dasharray: 6 6`).

**Trunk (today).** One smooth, slightly curved tapered shape in `--wood`, no bark texture. On it, a rounded label (card) with the health indicator: three small pills (liquidity months · debt ratio · goal feasibility). Trunk width can grow a little with net worth (cap ×1.3).

**Branches (decisions).**
- Chosen path: `--wood`, stroke 10–14px with ink outline, ends in a round foliage cloud (a "cloud of circles": draw circles with 8px ink stroke first, then same circles without stroke on top) coloured by that node's health.
- Visible options (siblings/children): same shape, 70% thickness.
- **Not chosen (grey):** `--ghost` wood and foliage, outline `--ink` at 35% opacity, foliage without fruits, `opacity: .65`. Still clickable (hover: back to 90% opacity + tooltip "compare"). Never red, never crossed out: a ghost branch is "a road you can still compare", not "wrong".
- Pruned branches simply fade out (300 ms) — no falling animation, to keep it calm.
- Label each branch with a short pill on the branch (card bg, ink text), e.g. "Master's", "Start working".

**Fruits (savings buffer).** `--fruit` circles r=6 on healthy foliage; number of fruits ≈ months of liquidity (cap 6). They drop to the ground when a shock hits.

**Leaves (explanation).** Clicking a node opens a leaf-shaped panel: card with a leaf-shaped tab on top (the same leaf path as the character's leaves) in the node's health colour. Content: metrics, comparison with siblings, Monte Carlo band chart, key assumption. Charts: line in `--ink`, band in node health colour at 25% opacity, median dashed.

**Weather (shocks you don't choose).** Applied to a node as an overlay, not a new branch:
- Calm: sky `--sky-calm`, small sun (yellow `--fruit` circle with ink outline).
- Inflation: warm haze, sun bigger and orange tint; leaves slightly yellower.
- Recession / job loss: grey cloud(s) `--sky-storm` with ink outline above the node + rain drops `--rain` (short rounded lines falling, CSS animation).
- Market drawdown: wind — 3 curved ink lines, foliage sways (`rotate(±3deg)`), 1–2 fruits fall.
- Badge on the node: weather icon + name, so it is never only colour.

## 4. Character in the scene: Lumi

The character is **not a tree**: **Lumi** is a soft glowing orb that floats next to the tree (`guide/`). No outline: a pale pearly sphere with a white shine, a soft inner shade, a halo, small dark pill eyes (`#1F2B4D`), a tiny mouth and pink blush. It is the only element with gradients and glow, so it reads as "the guide", separate from the flat tree.

- **Use it:** `import { createGuide } from ".../assets/character/guide/guide.js"` and `import ".../guide.css"`, then `createGuide(div, { health })`. API: `setHealth("healthy"|"fair"|"weak")`, `setPose("idle"|"explaining")`, `setTalking(bool)`, `moveTo(x, y)`, `destroy()`. Demo: open `guide/demo.html`.
- **Size:** set the host element width (default 140 px, 5:6 ratio); ~90 px on mobile.
- **Health = health of the currently selected node.** Healthy: mint, smiling, bright halo. Fair: warm yellow, neutral mouth, slightly squashed. Weak: pale grey-beige, short worried eyes, sinks and flattens, dim halo. Health changes cross-fade (0.4 s).
- **Explaining:** leans and looks toward the right, mouth open, sparkles. Place the leaf panel to its right (or mirror the host with `scaleX(-1)` if the panel is on the left; the face stays readable).
- **Moving:** `moveTo` glides with a slight overshoot and a jelly stretch. Glide to the side of the leaf panel, explain, then come back next to the trunk.
- Respects `prefers-reduced-motion` (no float, glide or squash).
- Static images of every state: `guide/states/lumi-<healthy|fair|weak>-<idle|explaining>.svg`. Regenerate states and demo with `node web/assets/character/guide/export.mjs`.

## 5. Type

Rounded but readable: `"Nunito", system-ui, sans-serif` (Google Fonts) for UI text; numbers with `font-variant-numeric: tabular-nums`.
