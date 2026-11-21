# web/src/personalize: "Make it mine" (owner: thread 7)

The user attaches their own condition to a branch, by text or voice. They confirm an editable proposal, and the branch re-grows (`docs/plan.md`, "Personal conditions → the tree re-grows"). Everything is exported from `index.js`.

## Mount (thread 6, `main.jsx`)

```jsx
import { MakeItMine, YourConditions, personalFields, personalStore, PROPOSAL_EVENT } from './personalize/index.js';

// 1. Send the session's conditions with EVERY engine request (/tree/expand, /tree/explore).
//    The path report (web/src/report) already does this for its own requests.
const body = { path: p, assumptions, uncertainty, exploration, ...personalFields() };

// 2. "Make it mine" on the current branch (not on the root).
{cur && cur.node_id !== '0' && <MakeItMine
  lang={lang} node={cur} path={path} profile={profile} assumptions={overrides}
  tr={(n) => translateNode(n, lang)}
  labelOf={(id) => tree.assumptions.find((a) => a.id === id)?.label || id}
  onConfirm={(item, fields) => go(path, { force: true })}   // re-expand: the branch re-grows
  onOpenChange={(open) => { /* e.g. pause narration or hide the bubble */ }}
  compact />}

// 3. The list of the user's conditions, with remove buttons.
<YourConditions lang={lang} onChange={(items, fields) => go(path, { force: true })} />

// 4. Mark custom branches: an engine node with `custom: true` or `origin: "user"`,
//    or personalStore.isCustom(node_id).
```

- Props of `MakeItMine`: `lang`, `node` ({node_id, parent_id, label, description}), `path`, `profile`, `assumptions`, `tr`, `labelOf`, `onConfirm(item, fields)`, `onOpenChange(open)`, `proposal` (a chat proposal, see below), `defaultOpen`, `compact`, `store` (default `personalStore`), and `request` (inject a fetcher in tests).
- `personalStore`: `list()`, `add(item)`, `remove(id)`, `clear()`, `subscribe(fn)`, `requestFields()` → `{custom_nodes?, node_patches?}` (only non-empty keys), `forNode(id)`, `isCustom(id)`. It persists in `sessionStorage` (`cigala.personal.v1`). Every change also fires `window` `cigala:personal-change` with `{items, fields}`.
- Chat: when the agent returns a `personalize` proposal, either pass it as `proposal={…}` or run `dispatchEvent(new CustomEvent(PROPOSAL_EVENT, { detail: { ...answer.personalize, node_id } }))`. The panel opens on that proposal, or on its clarifying question.
- The panel is a self-contained card (`.pz`), about 420 px wide, with light/dark and phone styles. Escape closes it. The mic uses the browser's speech recognition in the UI language. If the browser has none, the mic button is disabled.

## Expected `POST /tree/personalize` (thread 2)

Request (`personalizeBody` in `api.js`):

```json
{"path": ["2"], "node_id": "2", "text": "I'd get a CHF 600/month scholarship", "language": "en", "assumptions": [],
 "history": [{"question": "...", "answer": "..."}], "profile": {}, "custom_nodes": [], "node_patches": []}
```

Response (`normalizeProposal` in `model.js` accepts this shape; it also accepts the proposal at top level, or under `personalize`):

```json
{"status": "proposal | clarify | unsupported", "question": "For how many months?", "message": "...", "source": "llm | rules",
 "proposal": {"mode": "patch | branch", "node_id": "2", "parent_id": "0", "label": "Master's with a CHF 600/month scholarship",
              "description": "...", "interventions": [{"param": "monthly_net_income", "op": "add", "value": 600, "from_month": 0, "to_month": 24, "label": "Scholarship"}],
              "conditions": ["optional plain-language lines"]}}
```

While the route returns 404/405, a browser-side reader (`mockPersonalize`) answers instead. It is marked as a preview in the UI and only uses numbers found in the user's words.

## What the engine receives (thread 1, core)

- `node_patches: [{node_id, label, interventions, origin: "user", id}]`: the interventions are applied on top of that node's own, so its whole subtree inherits them.
- `custom_nodes: [{node_id, parent_id, based_on, label, description, interventions, custom: true, origin: "user"}]`: a new sibling of `based_on`. It is expected to start from `based_on`'s interventions and add these. Ids are `u1`, `2.u1`, … and unique per session.
