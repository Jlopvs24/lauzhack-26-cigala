// POST /tree/personalize (thread 2): the server's language model turns the user's words into the
// intervention schema, using only this node's levers and the user's own numbers, and may ask one question.
// Until the route is deployed (404/405) the browser-side reader in model.js answers instead, marked `mock`.
import { apiRequest } from '../api.js';
import { mockPersonalize, normalizeProposal } from './model.js';
import { personalFields } from './store.js';

export function personalizeBody({ profile, path = [], node, text, lang = 'en', assumptions = [], history = [], fields = personalFields() }) {
  return { path, node_id: node?.node_id, text, language: lang, assumptions, ...(history.length ? { history } : {}), ...(profile ? { profile } : {}), ...fields };
}

export async function requestPersonalization(args, { request = apiRequest, signal } = {}) {
  const { node, text, lang = 'en', tr = (n) => ({ label: n?.label }) } = args;
  const ctx = { node_id: node?.node_id, parent_id: node?.parent_id, text };
  try {
    const r = await request('/tree/personalize', { body: personalizeBody(args), signal });
    return normalizeProposal(r, ctx);
  } catch (e) {
    if (!/ 40[45]\b/.test(e?.message || '')) throw e;
    return normalizeProposal(mockPersonalize({ text, node_id: node?.node_id, parent_id: node?.parent_id, label: tr(node || {}).label || node?.label || '', lang }), ctx);
  }
}
