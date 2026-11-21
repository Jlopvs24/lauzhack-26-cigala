// Changes asked for in the chat go straight onto the tree (Lluc, #117 follow-up): no Make-it-mine confirm step.
// The API decides the shape (a what-if question grows a new branch under the current node; a statement or
// "on this branch" changes the current branch) and has already simulated it; this only stores it, and the
// store's change event makes the app re-expand the tree with it.
import { buildItem, normalizeProposal } from './model.js';
import { personalStore } from './store.js';

/** Apply the agent's `personalize` answer field; returns the stored item, or null if it holds no change. */
export function applyFromChat(raw, { node_id, parent_id = null, nodeLabel = '', store = personalStore } = {}) {
  const n = normalizeProposal(raw, { node_id, parent_id });
  if (n.status !== 'proposal') return null;
  const taken = store.list().map((i) => i.custom_node?.node_id).filter(Boolean);
  const item = buildItem(n.proposal, { mode: n.proposal.mode, label: n.proposal.label, takenIds: taken, nodeLabel });
  return store.add(item);
}
