// POST /tree/personalize (thread 2): the server's language model turns the user's words into the
// intervention schema, using only this node's levers and the user's own numbers, and may ask one question.
// Until the route is deployed (404/405) the browser-side reader in model.js answers instead, marked `mock`.
import { apiRequest } from '../api.js';
import { mockPersonalize, normalizeProposal } from './model.js';
import { personalFields } from './store.js';

export function personalizeBody({ profile, path = [], node, text, lang = 'en', assumptions = [], history = [], fields = personalFields() }) {
  return { path, node_id: node?.node_id, text, language: lang, assumptions, ...(history.length ? { history } : {}), ...(profile ? { profile } : {}), ...fields };
}

export const PERSONALIZE_TIMEOUT_MS = 20000;
export const isTimeout = (e) => e?.name === 'TimeoutError' || /timed? ?out/i.test(e?.message || '');

export async function requestPersonalization(args, { request = apiRequest, signal, timeoutMs = PERSONALIZE_TIMEOUT_MS } = {}) {
  const { node, text, lang = 'en', tr = (n) => ({ label: n?.label }) } = args;
  const ctx = { node_id: node?.node_id, parent_id: node?.parent_id, text };
  // its own deadline (shorter than api.js's global 30 s), still cancellable by the caller
  const both = AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)].filter(Boolean));
  try {
    const r = await request('/tree/personalize', { body: personalizeBody(args), signal: both });
    return normalizeProposal(r, ctx);
  } catch (e) {
    if (!/ 40[45]\b/.test(e?.message || '')) throw e;
    return normalizeProposal(mockPersonalize({ text, node_id: node?.node_id, parent_id: node?.parent_id, label: tr(node || {}).label || node?.label || '', lang }), ctx);
  }
}

// Manual fallback: the user's own numbers in the intervention schema. `per` month|year; months are 1-based.
export function manualIntervention({ kind = 'income', amount, per = 'month', from = 1, to = '' }) {
  const v = Number(amount);
  if (!Number.isFinite(v) || v <= 0) return null;
  const a = Math.max(0, (Number(from) || 1) - 1), b = Number(to);
  if (kind === 'one_off') return { param: 'one_off_cost', month: a, value: v, label: 'Your one-off cost' };
  const win = { from_month: a, ...(Number.isFinite(b) && b > a ? { to_month: b } : {}) };
  const monthly = per === 'year' ? Math.round((v / 12) * 100) / 100 : v;
  if (kind === 'rent') return { param: 'monthly_rent', op: 'set', value: monthly, ...win, label: 'Your rent' };
  if (kind === 'other') return { param: 'monthly_other_expenses', op: 'add', value: monthly, ...win, label: 'Your extra cost' };
  return { param: 'monthly_net_income', op: 'add', value: monthly, ...win, label: 'Your extra income' };
}
// Prefill the manual form from the browser-side reader's guess, if it found one.
export function manualFromGuess(r) {
  const iv = r?.proposal?.interventions?.[0];
  if (!iv) return { kind: 'income', amount: '', per: 'month', from: 1, to: '' };
  const kind = iv.param === 'monthly_rent' ? 'rent' : iv.param === 'monthly_other_expenses' ? 'other' : iv.param === 'one_off_cost' ? 'one_off' : 'income';
  return { kind, amount: iv.value ?? '', per: 'month', from: (iv.from_month ?? iv.month ?? 0) + 1, to: iv.to_month ?? '' };
}
