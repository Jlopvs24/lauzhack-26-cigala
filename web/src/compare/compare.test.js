import test from 'node:test';
import assert from 'node:assert/strict';
import { compareSiblings, cardCompareHTML, chipText, optionPaths, buildComparison, onlyDifferences, markExtremes, seriesOf, pathKey } from './model.js';
import { createCompareStore } from './store.js';
import { fromExpand, normalizeServer, loadComparison } from './data.js';

const res = (nw, min, extra = {}) => ({
  metrics: { final_net_worth_real: nw, final_net_worth: nw * 1.1, min_cash: min, min_cash_month: 20, first_negative_month: min < 0 ? 19 : null, liquidity_months: min / 1000, final_debt: 0 },
  plan_check: { level: min < 0 ? 'needs_financing' : 'holds' }, goals: [{ met_deterministic: min >= 0 }, { met_deterministic: true }],
  deterministic: { net_worth_real: [0, nw / 2, nw], cash: [0, min, nw] }, weather_resilience: { holds_in: min < 0 ? 0 : 3, of: 4, by_weather: [{ type: 'recession', holds: min >= 0 }] },
  assumptions_used: [{ id: 'AS-a', value: 0.01 }, { id: 'AS-s', value: nw > 100000 ? 4800 : 4200 }], ...extra,
});
const tree = {
  current: '2', path: ['0', '2'],
  nodes: [
    { node_id: '0', status: 'chosen', parent_id: null, label: 'Today', result: res(90000, 1000) },
    { node_id: '2', status: 'chosen', is_current: true, parent_id: '0', label: "Do a master's", result: res(100000, -18000) },
    { node_id: '1', status: 'sibling', parent_id: '0', label: 'Start working', result: res(112000, 30000) },
    { node_id: '3', status: 'sibling', parent_id: '0', label: 'Move abroad', result: res(60000, 2000) },
    { node_id: '2.1', status: 'child', parent_id: '2', label: 'Student job', result: res(95000, -20000) },
    { node_id: '2.2', status: 'child', parent_id: '2', label: 'Loan', result: res(99000, 3000) },
  ],
  assumptions: [{ id: 'AS-s', label: 'Salary', unit: 'CHF/month' }],
};

test('compareSiblings puts each option on a shared scale among its peers', () => {
  const c = compareSiblings(tree.nodes);
  assert.equal(c['1'].rank, 1); assert.equal(c['1'].pos, 1); assert.equal(c['3'].pos, 0); assert.equal(c['2'].n, 3);
  assert.equal(c['2.1'].n, 2); assert.equal(c['0'], undefined);
  // highest vs the next one down; the others vs the highest
  assert.equal(c['1'].chips[0].peer_id, '2'); assert.equal(Math.round(c['1'].chips[0].delta), 12000);
  assert.equal(c['3'].chips[0].peer_id, '1'); assert.ok(c['3'].chips[0].delta < 0);
  // funding gap against the others
  assert.deepEqual(c['2'].chips.find((x) => x.kind === 'gap_vs_none'), { kind: 'gap_vs_none', count: 2, tone: 'bad' });
  assert.equal(c['1'].chips.find((x) => x.kind === 'no_gap_vs').count, 1);
  assert.equal(c['2'].tone, 'bad'); assert.equal(c['1'].tone, 'good');
});

test('chip text and card HTML are translated, escaped and never say "best"', () => {
  const c = compareSiblings(tree.nodes);
  assert.equal(chipText(c['1'].chips[0], 'en'), "+CHF 12k vs Do a master's");
  assert.match(chipText(c['3'].chips[0], 'es'), /^−CHF 52k vs Start working$/);
  const html = cardCompareHTML(tree.nodes[1], tree.nodes, { lang: 'de', cmp: c });
  assert.match(html, /ccs-me bad/); assert.match(html, /role="img"/); assert.match(html, /andere haben keine/);
  assert.doesNotMatch(html, /best|mejor|meilleur|beste/i);
  assert.equal((cardCompareHTML(tree.nodes[1], tree.nodes, { compact: true, cmp: c }).match(/ccs-chip /g) || []).length, 1);
  assert.equal(cardCompareHTML(tree.nodes[0], tree.nodes), '');
  const evil = [{ ...tree.nodes[2], label: '<img>' }, tree.nodes[1]];
  assert.doesNotMatch(cardCompareHTML(tree.nodes[1], evil), /<img>/);
});

test('optionPaths: children of the current node, or the node and its siblings on a leaf', () => {
  assert.deepEqual(optionPaths(tree), [['2', '2.1'], ['2', '2.2']]);
  const leaf = { current: '2.2', path: ['0', '2', '2.2'], nodes: [{ node_id: '2.2', status: 'chosen' }, { node_id: '2.1', status: 'sibling' }] };
  assert.deepEqual(optionPaths(leaf), [['2', '2.2'], ['2', '2.1']]);
  assert.equal(pathKey(['0', '2', '2.1']), '2/2.1'); assert.equal(pathKey([]), '0');
});

test('compare store: max 4, no duplicates, persisted, broadcast', () => {
  const mem = new Map(); const storage = { getItem: (k) => mem.get(k) ?? null, setItem: (k, v) => mem.set(k, v) };
  const s = createCompareStore({ storage, target: null });
  let seen = 0; s.subscribe(() => { seen += 1; });
  assert.ok(s.add({ path: ['2'], label: 'A' })); assert.equal(s.add({ path: ['0', '2'], label: 'A' }), false);
  for (const p of ['1', '3', '2.1']) s.add({ path: [p], label: p });
  assert.equal(s.add({ path: ['9'] }), false); assert.ok(s.full());
  s.remove(['1']); assert.equal(s.list().length, 3); assert.equal(seen, 5);
  assert.equal(createCompareStore({ storage, target: null }).list().length, 3);
  s.prune((p) => p[0] !== '3'); assert.deepEqual(s.list().map((i) => i.key), ['2', '2.1']);
});

test('fallback columns from /tree/expand: parent, baseline, crumbs, personal markers', () => {
  const col = fromExpand({ ...tree, current: '2.2', path: ['0', '2', '2.2'], nodes: [...tree.nodes.map((n) => (n.node_id === '2.2' ? { ...n, status: 'chosen', is_current: true, patched: true } : n))] }, ['2', '2.2']);
  assert.equal(col.node_id, '2.2'); assert.equal(col.parent.node_id, '2'); assert.equal(col.baseline.metrics.final_net_worth_real, 90000);
  assert.deepEqual(col.crumbs.map((c) => c.id), ['2', '2.2']); assert.equal(col.personal[0].kind, 'patched');
  assert.equal(normalizeServer({ nope: 1 }), null);
});

test('/tree/compare options map onto the same columns (impact alone from the server deltas)', () => {
  const opt = (id, nw, gap, dParent, dToday) => ({ key: `x:${id}`, node_id: id, label: `L${id}`, path: ['0', '2', id], path_labels: ["Do a master's", `L${id}`],
    plan_check: { level: gap ? 'needs_financing' : 'holds' }, patched: id === '2.2',
    metrics: { final_net_worth_real: nw, min_cash: gap ? -gap : 100, min_cash_month: 3, first_negative_month: gap ? 2 : null, goals_met: 2, goals_total: 2, liquidity_months: 1, final_debt: 0 },
    series: { net_worth: [0, nw], net_worth_real: [0, nw], cash: [0, 5] },
    impact_alone: { vs_parent: { node_id: '2', delta: { final_net_worth_real: dParent, min_cash: 10, goals_met: 0 } }, vs_today: { node_id: '0', delta: { final_net_worth_real: dToday } } } });
  const cols = normalizeServer({ options: [opt('2.1', 100000, 18000, 0, 120000), opt('2.2', 117000, 0, 14900, 137000)] });
  assert.deepEqual(cols.map((c) => c.key), ['2/2.1', '2/2.2']);
  assert.deepEqual(cols[1].crumbs.map((c) => c.label), ["Do a master's", 'L2.2']);
  assert.equal(cols[1].personal[0].kind, 'patched');
  const cmp = buildComparison(cols);
  const impact = cmp.sections.find((s) => s.key === 'impact');
  assert.deepEqual(impact.rows.find((r) => r.key === 'vsParent').cells.map((c) => c.text), ['±CHF 0', '+CHF 14’900']);
  assert.equal(impact.rows.find((r) => r.key === 'vsToday').cells[1].mark, 'hi');
  assert.equal(cmp.sections[0].rows.find((r) => r.key === 'goals').cells[0].text, '2 of 2');
  assert.equal(seriesOf(cols)[0].values.at(-1), 100000);
});

test('buildComparison: grouped rows, highest/lowest marks, impact alone, differences only', () => {
  const cols = ['2', '1', '3'].map((id) => fromExpand(tree, [id]));
  cols[0].smallest = { already_holds: false, changes: [{ lever: 'more_income', status: 'threshold_found', value: 762 }, { lever: 'cash_now', status: 'threshold_found', value: 18531 }] };
  cols[1].smallest = { already_holds: true, changes: [] };
  const cmp = buildComparison(cols, { lang: 'en', weatherLabel: (t) => t });
  assert.deepEqual(cmp.sections.map((s) => s.key), ['outcome', 'impact', 'truth', 'stress', 'assumptions']);
  const nw = cmp.sections[0].rows.find((r) => r.key === 'nw');
  assert.deepEqual(nw.cells.map((c) => c.mark), [null, 'hi', 'lo']);
  const vsToday = cmp.sections[1].rows.find((r) => r.key === 'vsToday');
  assert.equal(vsToday.cells[1].text, '+CHF 22’000');
  assert.equal(cmp.sections[2].rows[0].cells[0].text, '+CHF 762/month income');
  assert.equal(cmp.sections[2].rows[0].cells[1].text, 'already no gap');
  assert.equal(cmp.sections[4].rows[0].label, 'Salary');
  const json = JSON.stringify(cmp);
  assert.doesNotMatch(json, /\bbest\b/i);
  const only = onlyDifferences(cmp.sections);
  assert.ok(only.every((s) => s.rows.every((r) => new Set(r.cells.map((c) => c.text)).size > 1)));
  assert.equal(markExtremes({ numeric: true, cells: [{ value: 1 }, { value: 1 }] }).cells[0].mark, undefined);
  assert.equal(seriesOf(cols)[1].values.at(-1), 112000);
});

test('loadComparison falls back to /tree/expand when /tree/compare is missing, and sends weather + conditions', async () => {
  const calls = [];
  const request = async (route, { body }) => {
    calls.push([route, body]);
    if (route === '/tree/compare') throw new Error('The API returned 404. Check the backend and try again.');
    if (route === '/tree/expand') return { ...tree, current: body.path.at(-1), path: ['0', ...body.path] };
    if (route === '/tree/smallest_change') return { already_holds: true, changes: [] };
    return null;
  };
  const fields = { node_patches: { 2: [{ param: 'one_off_income', month: 0, value: 1 }] } };
  const cols = await loadComparison({ paths: [['1'], ['3']], weather: [{ type: 'recession' }], fields, request });
  assert.deepEqual(cols.map((c) => c.node_id), ['1', '3']);
  assert.equal(cols[0].smallest.already_holds, true);
  assert.ok(calls.every(([, b]) => b.weather?.[0]?.type === 'recession' && b.node_patches));
  await assert.rejects(loadComparison({ paths: [['1'], ['3']], request: async () => { throw new Error('The API returned 500.'); } }));
});

test('one pinned path is compared with its alternatives (siblings), up to 4', async () => {
  const { withAlternatives } = await import('./data.js');
  const request = async (route, { body }) => ({ nodes: [{ node_id: body.path.at(-1), status: 'chosen' }, { node_id: '2.1', status: 'sibling' }, { node_id: '2.3', status: 'sibling' }, { node_id: '2.2.1', status: 'child' }] });
  assert.deepEqual(await withAlternatives(['2', '2.2'], { request }), [['2', '2.2'], ['2', '2.1'], ['2', '2.3']]);
  assert.deepEqual(await withAlternatives(['2'], { request: async () => { throw new Error('x'); } }), [['2']]);
});
