// Pure logic of "Make it mine": read a /tree/personalize answer (or a chat proposal), say each change in
// plain words with its numbers, let the user edit the amounts and the mode, and build the stored item with
// the `node_patch` or `custom_node` the engine receives. Also a small browser-side reader used only while
// POST /tree/personalize is not deployed: it takes numbers from the user's words and never invents one.
import { pi } from './i18n.js';

const MINUS = '−';
export const chf = (n) => (Number.isFinite(n) ? (n < 0 ? MINUS : '') + 'CHF ' + Math.abs(Math.round(n)).toLocaleString('en-US').replace(/,/g, '’') : '–');
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
let seq = 0;
export const newId = (prefix = 'pc') => `${prefix}-${Date.now().toString(36)}${(seq++).toString(36)}`;

const MONTHLY = new Set(['monthly_net_income', 'monthly_rent', 'monthly_other_expenses', 'monthly_investment_contribution']);
export const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

// The one amount of an intervention the user can edit (null when it has none or it references an assumption).
export function amountOf(iv) {
  if (!iv) return null;
  if (iv.param === 'new_liability') return isNum(iv.liability?.principal) ? iv.liability.principal : null;
  if (iv.param === 'loan_change') return isNum(iv.monthly_payment) ? iv.monthly_payment : null;
  return isNum(iv.value) ? iv.value : null;
}
export function withAmount(iv, v) {
  if (!Number.isFinite(v)) return iv;
  if (iv.param === 'new_liability') return { ...iv, liability: { ...iv.liability, principal: v } };
  if (iv.param === 'loan_change') return { ...iv, monthly_payment: v };
  return { ...iv, value: v };
}

// One intervention in plain words, in the UI language. `labelOf(id)` names an assumption.
export function describe(iv, lang = 'en', labelOf = (id) => id) {
  const L = pi(lang);
  if (!iv || typeof iv !== 'object') return '';
  const window = isNum(iv.from_month) && isNum(iv.to_month) ? L.months(iv.from_month + 1, iv.to_month) : isNum(iv.from_month) && iv.from_month > 0 ? L.fromM(iv.from_month + 1) : '';
  const v = iv.value, amt = isNum(v) ? chf(Math.abs(v)) : '';
  if (MONTHLY.has(iv.param)) {
    const what = L.w[iv.param];
    if (!isNum(v)) return cap(`${what}${window}`);
    if (iv.op === 'add') return L.add(v < 0 ? MINUS : '+', amt, what) + window;
    if (iv.op === 'mul') return L.mul(cap(what), Math.round(v * 100) / 100) + window;
    return L.set(cap(what), amt) + window;
  }
  if (iv.param === 'one_off_cost') return L.oneCost(amt, (iv.month ?? 0) + 1);
  if (iv.param === 'one_off_income') return L.oneIncome(amt, (iv.month ?? 0) + 1);
  if (iv.param === 'new_liability') {
    const l = iv.liability || {};
    return L.loan(chf(l.principal), isNum(l.annual_rate) ? Math.round(l.annual_rate * 1000) / 10 : '–', chf(l.monthly_payment));
  }
  if (iv.param === 'loan_change') return L.loanChange(iv.loan || '', chf(iv.monthly_payment), (iv.month ?? 0) + 1);
  if (iv.param === 'cancel_one_off') return L.cancelOne(iv.label || '');
  if (iv.param === 'assumption') return L.assumption(labelOf(iv.id), isNum(v) ? String(v) : '–');
  return iv.text || iv.label || iv.param || '';
}

// Accepts the /tree/personalize answer, a chat agent's `personalize` proposal, or a bare proposal.
// Returns {status: 'proposal' | 'clarify' | 'unsupported', question?, message?, proposal?}.
export function normalizeProposal(raw, ctx = {}) {
  const r = raw?.personalize || raw || {};
  const p = r.proposal || (r.interventions || r.custom_node || r.node_patch ? r : null);
  const question = r.question || r.clarifying_question || p?.question || null;
  const interventions = (p && (p.interventions || p.node_patch?.interventions || p.custom_node?.interventions)) || [];
  if (!p || !interventions.length) {
    if (question) return { status: 'clarify', question, source: r.source || 'api' };
    return { status: 'unsupported', message: r.message || r.reason || '', source: r.source || 'api' };
  }
  const branch = ['branch', 'new_branch', 'custom_node'].includes(p.mode) || (!p.mode && p.custom_node && !p.node_patch);
  return {
    status: 'proposal', question: null, source: r.source || p.source || 'api',
    proposal: {
      id: p.id || newId(), mode: branch ? 'branch' : 'patch',
      node_id: p.node_id || p.target_node_id || p.node_patch?.node_id || p.custom_node?.based_on || ctx.node_id,
      parent_id: p.parent_id ?? p.custom_node?.parent_id ?? ctx.parent_id ?? null,
      label: p.label || p.custom_node?.label || p.node_patch?.label || ctx.text || '',
      description: p.description || p.summary || '',
      interventions: interventions.map((x) => ({ ...x })),
      conditions: (p.conditions || []).map((c) => (typeof c === 'string' ? c : c?.text || '')),
      text: r.text || p.text || ctx.text || '',
    },
  };
}

// Custom branch ids: a sibling of the target, e.g. "2" -> "u1", "2.1" -> "2.u1". Unique in the store.
export function customNodeId(parentId, taken = []) {
  const base = !parentId || parentId === '0' ? '' : `${parentId}.`;
  let n = 1;
  while (taken.includes(`${base}u${n}`)) n++;
  return `${base}u${n}`;
}

// The stored item for a confirmed proposal. Patch: {node_id, interventions} applied on top of that node.
// Branch: a new sibling `based_on` the target (its interventions first, then the user's).
export function buildItem(proposal, { mode = proposal.mode, label = proposal.label, takenIds = [], nodeLabel = '' } = {}) {
  const base = { id: proposal.id || newId(), mode, node_id: proposal.node_id, label: (label || '').trim() || nodeLabel, text: proposal.text || '', interventions: proposal.interventions, conditions: proposal.conditions || [], created_at: new Date().toISOString(), node_label: nodeLabel };
  if (mode === 'branch') {
    const parent = proposal.parent_id ?? parentOf(proposal.node_id);
    const node_id = customNodeId(parent, takenIds);
    return { ...base, custom_node: { node_id, parent_id: parent || '0', based_on: proposal.node_id, label: base.label, description: proposal.description || base.text, interventions: proposal.interventions, custom: true, origin: 'user' } };
  }
  return { ...base, node_patch: { node_id: proposal.node_id, label: base.label, interventions: proposal.interventions, origin: 'user', id: base.id } };
}
export const parentOf = (id) => (!id || id === '0' ? null : id.includes('.') ? id.slice(0, id.lastIndexOf('.')) : '0');

// ---------------------------------------------------------------- browser-side reader (until the API lands)
const RX = {
  income: /scholar|grant|stipend|bursar|allowance|support|parents|bourse|beca|ayuda|subsid|stipendium|unterstützung|eltern|salary|salaire|salario|gehalt|lohn|earn|gagn|ganar|verdien|job|work|trabaj|travail|arbeit|freelanc|side/i,
  job: /job|work|trabaj|travail|arbeit|%/i,
  rent: /rent|loyer|alquiler|miete|room|chambre|habitaci|zimmer/i,
  invest: /invest|save|saving|épargn|ahorr|spar/i,
  oneOff: /once|one[- ]off|one time|laptop|computer|deposit|une fois|una vez|einmal|kaution|caution|fianza/i,
  costWord: /cost|pay|spend|buy|coût|payer|acheter|gasto|pagar|comprar|kost|zahl|kauf/i,
  branchWord: /instead|new branch|new option|compare|alternative|en vez|en lugar|plutôt|à la place|stattdessen|neuer ast|nueva rama|nouvelle branche/i,
};
function amounts(text) {
  // CHF amounts: "CHF 600", "600 CHF", "1'200", "1’800", "1,200", "1.200 Fr."; percents are excluded
  const out = [];
  const re = /(?:chf|fr\.?|sfr\.?)?\s*(\d{1,3}(?:[’',.\s]\d{3})+|\d+(?:[.,]\d+)?)\s*(k\b)?\s*(%)?/gi;
  let m;
  while ((m = re.exec(text))) {
    if (m[3]) continue;
    let s = m[1].replace(/[’'\s]/g, '');
    if (/^\d{1,3}([.,]\d{3})+$/.test(s)) s = s.replace(/[.,]/g, ''); else s = s.replace(',', '.');
    const v = parseFloat(s) * (m[2] ? 1000 : 1);
    if (Number.isFinite(v) && v > 0) out.push(v);
  }
  return out;
}
function duration(text) {
  const m = text.match(/(\d+)\s*(months?|mois|mes(?:es)?|monate?n?)\b/i);
  if (m) return +m[1];
  const y = text.match(/(\d+)\s*(years?|ans?|años?|jahre?n?)\b/i);
  return y ? +y[1] * 12 : null;
}

export function mockPersonalize({ text = '', node_id, parent_id, label = '', lang = 'en' } = {}) {
  const L = pi(lang), t = text.trim();
  const nums = amounts(t.replace(/\d+\s*(months?|mois|mes(?:es)?|monate?n?|years?|ans?|años?|jahre?n?)\b/gi, ''));
  const months = duration(t);
  const win = months ? { from_month: 0, to_month: months } : { from_month: 0 };
  const mode = RX.branchWord.test(t) ? 'branch' : 'patch';
  const short = t.length > 48 ? t.slice(0, 47).trimEnd() + '…' : t;
  const out = (iv) => ({ status: 'proposal', source: 'mock', text: t, proposal: { mode, node_id, parent_id, label: mode === 'branch' && label ? `${label} · ${short}` : short, interventions: [iv], conditions: [] } });
  if (!nums.length) {
    if (RX.job.test(t) && /\d+\s*%/.test(t)) return { status: 'clarify', source: 'mock', question: L.q.job };
    return { status: 'clarify', source: 'mock', question: L.q.amount };
  }
  const v = nums[0];
  if (RX.rent.test(t)) return out({ param: 'monthly_rent', op: 'set', value: v, ...win, label: 'Your rent' });
  if (RX.oneOff.test(t)) {
    return RX.income.test(t) && !RX.costWord.test(t) ? out({ param: 'one_off_income', month: 0, value: v, label: 'Your one-off income' })
      : out({ param: 'one_off_cost', month: 0, value: v, label: 'Your one-off cost' });
  }
  if (RX.invest.test(t)) return out({ param: 'monthly_investment_contribution', op: 'add', value: v, ...win, label: 'Your monthly investing' });
  if (RX.costWord.test(t) && !RX.income.test(t)) return out({ param: 'monthly_other_expenses', op: 'add', value: v, ...win, label: 'Your extra cost' });
  if (RX.income.test(t)) return out({ param: 'monthly_net_income', op: 'add', value: v, ...win, label: 'Your extra income' });
  return { status: 'clarify', source: 'mock', question: L.q.dir };
}
