import test from 'node:test';
import assert from 'node:assert/strict';
import { createPersonalStore, requestFieldsOf } from './store.js';
import { amountOf, buildItem, customNodeId, describe, mockPersonalize, normalizeProposal, parentOf, withAmount } from './model.js';
import { personalizeBody, requestPersonalization } from './api.js';
import { PI } from './i18n.js';

const memory = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), removeItem: (k) => m.delete(k) }; };
const scholarship = { param: 'monthly_net_income', op: 'add', value: 600, from_month: 0, to_month: 24, label: 'Scholarship' };

test('store: add / remove / list, persisted, request fields only when non-empty, subscribers and events', () => {
  const storage = memory(), events = [];
  const target = { dispatchEvent: (e) => events.push(e) };
  globalThis.CustomEvent ??= class extends Event { constructor(t, o) { super(t); this.detail = o?.detail; } };
  const s = createPersonalStore({ storage, target });
  assert.deepEqual(s.requestFields(), {});
  const seen = [];
  const off = s.subscribe((items) => seen.push(items.length));
  const patch = buildItem({ id: 'a', mode: 'patch', node_id: '2', interventions: [scholarship], label: 'With scholarship' });
  const branch = buildItem({ id: 'b', mode: 'branch', node_id: '2', interventions: [scholarship], label: 'Master’s with scholarship' }, { takenIds: [] });
  s.add(patch); s.add(branch);
  assert.deepEqual(s.list().map((i) => i.id), ['a', 'b']);
  assert.deepEqual(s.requestFields(), { custom_nodes: [branch.custom_node], node_patches: [patch.node_patch] });
  assert.equal(s.isCustom('u1'), true);
  assert.deepEqual(s.forNode('2').map((i) => i.id), ['a']);
  // a second store on the same storage sees the same items (sessionStorage persistence)
  assert.equal(createPersonalStore({ storage, target: null }).list().length, 2);
  s.remove('a');
  assert.deepEqual(s.requestFields(), { custom_nodes: [branch.custom_node] });
  off(); s.clear();
  assert.deepEqual(seen, [1, 2, 1]);
  assert.equal(events.length, 4);
  assert.equal(events.at(-1).type, 'cigala:personal-change');
  assert.deepEqual(events.at(-1).detail.fields, {});
  assert.deepEqual(requestFieldsOf([]), {});
  // corrupt storage never breaks the app
  const bad = memory(); bad.setItem('cigala.personal.v1', '{nope');
  assert.deepEqual(createPersonalStore({ storage: bad, target: null }).list(), []);
});

test('items: a patch targets the node, a branch is a new sibling based on it with a unique id', () => {
  const p = buildItem({ id: 'x', mode: 'patch', node_id: '2.1', interventions: [scholarship], label: ' ' }, { nodeLabel: 'Student job only' });
  assert.equal(p.label, 'Student job only');
  assert.deepEqual(p.node_patch, { node_id: '2.1', label: 'Student job only', interventions: [scholarship], origin: 'user', id: 'x' });
  const b = buildItem({ mode: 'branch', node_id: '2.1', interventions: [scholarship], label: 'Mine' }, { takenIds: ['2.u1'] });
  assert.equal(b.custom_node.node_id, '2.u2');
  assert.equal(b.custom_node.parent_id, '2');
  assert.equal(b.custom_node.based_on, '2.1');
  assert.equal(b.custom_node.custom, true);
  assert.equal(customNodeId('0', []), 'u1');
  assert.equal(parentOf('2'), '0');
  assert.equal(parentOf('2.1.3'), '2.1');
});

test('plain words in every language, with editable amounts', () => {
  assert.equal(describe(scholarship, 'en'), '+CHF 600/month income, months 1–24');
  assert.equal(describe(scholarship, 'de'), '+CHF 600/Monat Einkommen, Monate 1–24');
  assert.equal(describe({ param: 'monthly_rent', op: 'set', value: 750, from_month: 0 }, 'en'), 'Rent: CHF 750/month');
  assert.equal(describe({ param: 'one_off_cost', month: 0, value: 1200 }, 'fr'), 'Dépense unique de CHF 1’200 au mois 1');
  assert.match(describe({ param: 'new_liability', month: 0, liability: { principal: 15000, annual_rate: 0.02, monthly_payment: 300 } }, 'es'), /CHF 15’000 al 2%/);
  assert.equal(describe({ param: 'assumption', id: 'AS-x', value: 0.5 }, 'en', () => 'Return'), 'Return: 0.5');
  assert.equal(amountOf(scholarship), 600);
  assert.equal(amountOf(withAmount(scholarship, 800)), 800);
  assert.equal(amountOf({ param: 'monthly_net_income', value: { assumption: 'AS-x' } }), null);
});

test('proposals: API answer, chat agent shape, clarifying question, unsupported', () => {
  const api = normalizeProposal({ status: 'proposal', proposal: { mode: 'patch', node_id: '2', label: 'With scholarship', interventions: [scholarship] } });
  assert.equal(api.status, 'proposal');
  assert.equal(api.proposal.mode, 'patch');
  assert.equal(api.proposal.node_id, '2');
  const chat = normalizeProposal({ personalize: { custom_node: { parent_id: '0', based_on: '2', label: 'Master + 40% job', interventions: [scholarship] } } });
  assert.equal(chat.proposal.mode, 'branch');
  assert.equal(chat.proposal.node_id, '2');
  const q = normalizeProposal({ status: 'clarify', question: 'For how many months?' });
  assert.deepEqual([q.status, q.question], ['clarify', 'For how many months?']);
  assert.equal(normalizeProposal({ status: 'unsupported', message: 'no' }).status, 'unsupported');
  assert.equal(normalizeProposal(null).status, 'unsupported');
});

test('browser-side reader: only the user’s numbers, a question when one is missing', () => {
  const s = mockPersonalize({ text: 'I’d get a CHF 600/month scholarship for 2 years', node_id: '2', parent_id: '0', label: 'Do a master’s' });
  assert.equal(s.status, 'proposal');
  assert.deepEqual(s.proposal.interventions[0], { param: 'monthly_net_income', op: 'add', value: 600, from_month: 0, to_month: 24, label: 'Your extra income' });
  assert.equal(mockPersonalize({ text: 'Mi alquiler sería de CHF 750 al mes', lang: 'es' }).proposal.interventions[0].param, 'monthly_rent');
  assert.equal(mockPersonalize({ text: "I'd work 40% alongside for CHF 1'800/month" }).proposal.interventions[0].value, 1800);
  assert.equal(mockPersonalize({ text: 'I would work 40% alongside', lang: 'de' }).question, PI.de.q.job);
  assert.equal(mockPersonalize({ text: 'a scholarship' }).status, 'clarify');
  assert.equal(mockPersonalize({ text: 'instead, a laptop once for CHF 1.500' }).proposal.mode, 'branch');
  assert.equal(mockPersonalize({ text: 'instead, a laptop once for CHF 1.500' }).proposal.interventions[0].value, 1500);
});

test('API: posts text, node and the session conditions; falls back to the reader only on 404/405', async () => {
  const node = { node_id: '2', parent_id: '0', label: 'Do a master’s' };
  const fields = { node_patches: [{ node_id: '2.1', interventions: [] }] };
  assert.deepEqual(personalizeBody({ path: ['2'], node, text: 'hi', lang: 'fr', fields }), { path: ['2'], node_id: '2', text: 'hi', language: 'fr', assumptions: [], node_patches: fields.node_patches });
  let sent;
  const ok = await requestPersonalization({ path: ['2'], node, text: 'x' }, { request: async (route, { body }) => { sent = [route, body]; return { status: 'clarify', question: '¿Cuánto?' }; } });
  assert.equal(sent[0], '/tree/personalize');
  assert.equal(ok.question, '¿Cuánto?');
  const mock = await requestPersonalization({ path: ['2'], node, text: 'CHF 600 a month scholarship' }, { request: async () => { throw new Error('The API returned 404. Check the backend and try again.'); } });
  assert.equal(mock.source, 'mock');
  assert.equal(mock.proposal.interventions[0].value, 600);
  await assert.rejects(requestPersonalization({ node, text: 'x' }, { request: async () => { throw new Error('The API returned 500.'); } }), /500/);
});

test('every language has every English string', () => {
  const shape = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, Array.isArray(v) ? `array${v.length}` : typeof v === 'object' ? shape(v) : typeof v]));
  for (const lang of ['es', 'fr', 'de']) assert.deepEqual(shape(PI[lang]), shape(PI.en), lang);
});
