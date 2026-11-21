// Changes asked for in the chat go straight onto the tree (Lluc, #117 follow-up): no Make-it-mine confirm step.
// The API decides the shape (a what-if question grows a new branch under the current node; a statement or
// "on this branch" changes the current branch) and has already simulated it; this only stores it, and the
// store's change event makes the app re-expand the tree with it.
// "undo" / "make it 400 instead" act on the last change made from the chat: the app sends it as
// context.last_change and applies the API's `tree_action`.
import { buildItem, normalizeProposal } from './model.js';
import { personalStore } from './store.js';

/** Apply the agent's `personalize` answer field; returns the stored item, or null if it holds no change. */
export function applyFromChat(raw, { node_id, parent_id = null, nodeLabel = '', store = personalStore } = {}) {
  const n = normalizeProposal(raw, { node_id, parent_id });
  if (n.status !== 'proposal') return null;
  const taken = store.list().map((i) => i.custom_node?.node_id).filter(Boolean);
  const item = buildItem(n.proposal, { mode: n.proposal.mode, label: n.proposal.label, takenIds: taken, nodeLabel });
  return store.add({ ...item, source: 'chat' });
}

/** The last change the chat made, in the shape the API reads (context.last_change), or null. */
export function lastChatChange(store = personalStore) {
  const it = store.list().filter((i) => i.source === 'chat').at(-1);
  if (!it) return null;
  const branch = it.mode === 'branch';
  return { id: it.id, mode: branch ? 'branch' : 'patch', label: it.label,
    node_id: branch ? it.custom_node?.parent_id : it.node_id, custom_id: branch ? it.custom_node?.node_id : null,
    interventions: (branch ? it.custom_node?.interventions : it.node_patch?.interventions) || it.interventions || [] };
}

/** Apply the API's tree_action: {type: 'undo', id} removes it; {type: 'replace', id, interventions, label} edits it. */
export function applyTreeAction(action, store = personalStore) {
  if (!action?.id) return null;
  const it = store.get(action.id);
  if (!it) return null;
  if (action.type === 'undo') { store.remove(action.id); return { removed: it }; }
  if (action.type === 'replace' && Array.isArray(action.interventions) && action.interventions.length) {
    const ivs = action.interventions.map((x) => ({ ...x }));
    const label = action.label || it.label;
    const next = it.mode === 'branch'
      ? { ...it, label, interventions: ivs, custom_node: { ...it.custom_node, label, interventions: ivs } }
      : { ...it, label, interventions: ivs, node_patch: { ...it.node_patch, interventions: ivs.map((x) => ({ source: 'user', ...x })) } };
    return { replaced: store.add(next) };
  }
  return null;
}
