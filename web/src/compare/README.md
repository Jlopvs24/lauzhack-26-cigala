# web/src/compare (owner: thread 10)

This folder answers the user's question "How are the options compared?" It has three parts:

- **Comparative cards.** Each option card shows where it sits among its sibling options, and how it differs from them.
- **Compare these options.** One click opens a spec-style comparison page for the options visible here.
- **Pins across branches.** A **+** on any card or report adds that path to a tray of up to 4 paths. A sticky bar then opens the same page for the pinned paths.

Every number comes from the engine. The page never says "best". In each row it marks the highest and lowest values with a tint and a word.

## Mount points

```jsx
import { CompareRoot, CardCompareStrip, AddToCompare, CompareOptionsButton, cardCompareHTML, pinHTML, openCompare } from './compare/index.js';
```

**Thread 6 (`main.jsx`, scene cards)**

1. Mount `<CompareRoot>` once, inside `App` after the report drawer:
   ```jsx
   {started && <CompareRoot lang={lang} tr={(n) => translateNode(n, lang)} profile={profile} assumptions={overrides} weather={tree?.weather} />}
   ```
   It renders the sticky compare bar (bottom centre, `.cmp-bar`; move it if it collides with the dock) and, when opened, the comparison page. It also handles the clicks on the HTML `+` pins. Personal conditions come from `web/src/personalize`. If `weather` is omitted, it uses the last `weather:change` event.
2. Add the card strip in `tagMeta(n, lang)`. The cards are HTML strings, so use the string version and append it after slot B:
   ```js
   + cardCompareHTML(n, state.current.tree?.nodes || [], { lang, label: (id, l) => translateNode({ node_id: id, label: l }, lang).label })
   ```
   On phones, pass `compact: true` to keep only the scale and one chip (the CSS also hides the second chip at ≤720px). The React version is `<CardCompareStrip node={n} siblings={tree.nodes} lang tr />`.
3. Add a `+` pin on each child or sibling card: `pinHTML(pathOfNode, translatedLabel, lang)`. Here `pathOfNode` is `[...target, id]` for a child and `[...target.slice(0, -1), id]` for a sibling. Insert it in the card markup or append it to `meta`. Clicks on it are caught in the capture phase, so the card does not navigate.
4. Add the one-click button "Compare these options", e.g. next to Back or in the header: `<CompareOptionsButton tree={tree} lang={lang} />`. It shows the current node's children, or the node and its siblings on a leaf, and renders nothing when there are fewer than 2 options. You can also call `openCompare({ paths })` from anywhere; with no `paths`, it opens the pinned selection.

**Thread 7 (path report header, leaf cards)**

```jsx
<AddToCompare path={path} label={tr(leafNode).label} lang={lang} />            // pill: "+ Add to comparison"
<AddToCompare path={path} label={...} lang={lang} variant="icon" />            // round icon only
```

## Data

`loadComparison` in `data.js` is the single switch point. It first tries `POST /tree/compare` with `{paths, baseline: [], assumptions, weather, custom_nodes?, node_patches?, profile?}`. If that route is missing (404/405/501), or its response shape is not one `normalizeServer` can read, it falls back to the routes that already exist:

- one `/tree/expand` per path, which gives the node, its parent ("this choice alone") and the root "today";
- `/tree/explore`, `/tree/smallest_change` and `/tree/timing_scan` for the "what would have to be true" rows.

The outcome rows show first and the what-if rows fill in after.

## Dev harness

`/src/compare/demo.html?path=2&lang=es&theme=dark` (not in the build) shows real API cards with the strip, the pins, the bar and the page.
