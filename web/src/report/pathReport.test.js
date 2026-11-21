import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildFromLevels, loadExploration, loadLevels, loadSummary, mergeExploration } from './pathReport.js';

const load = (f) => JSON.parse(readFileSync(new URL(`../../../core/examples/${f}`, import.meta.url), 'utf8'));
const levels = { '': load('expand_alexia_root.json'), 2: load('expand_alexia_2.json') };

test('stage 1: one expand per level, in parallel, the lens only on the leaf', async () => {
  const calls = [];
  const expand = async (p, leaf) => { calls.push([p.join('.'), leaf]); return levels[p.join('.')]; };
  const lv = await loadLevels({ path: ['2'], uncertainty: true, expand });
  assert.deepEqual(calls, [['', false], ['2', true]]);
  const d = buildFromLevels(lv, { path: ['2'] });
  assert.equal(d.source, 'expand');
  assert.equal(d.steps.length, 1);
  assert.equal(d.steps[0].node_id, '2');
  assert.deepEqual(d.steps[0].alternatives.map((a) => a.node_id).sort(), ['1', '3']);
  assert.equal(d.steps[0].summary.first_negative_month, 6);
  assert.equal(d.leaf.plan_check.level, 'needs_financing');
  assert.equal(d.leaf.node_id, '2');
  // the over-time chart: the leaf and its siblings with monthly series
  assert.deepEqual(d.leaf.peers.map((p) => p.node_id).sort(), ['1', '2', '3']);
  assert.equal(d.leaf.peers.find((p) => p.chosen).node_id, '2');
  assert.ok(d.leaf.peers.every((p) => p.cash.length === 121 && p.net_worth.length === 121));
  assert.equal(d.leaf.bands, null); // lens asked but not computed in the fixture: no band
  assert.equal(d.stress[0].weather, 'none');
  assert.equal(d.stress.length, 1 + d.leaf.weather_resilience.by_weather.length);
  assert.ok(d.assumptions.length > 10);
  assert.ok(d.steps[0].delta_vs_parent.final_net_worth_real > 0);
});

test('stage 2: exploration per step is merged without touching the rest', async () => {
  const d = buildFromLevels([levels[''], levels[2]], { path: ['2'] });
  const ex = { reverse_stress: { status: 'threshold_found', value: 1234 } };
  const got = await loadExploration({ path: ['2'], explore: async (p) => ({ node_id: p.at(-1), exploration: ex, sensitivity: [], facts: ['f'] }) });
  const m = mergeExploration(d, got);
  assert.equal(m.explored, true);
  assert.equal(m.steps[0].result.exploration, ex);
  assert.deepEqual(m.steps[0].facts, ['f']);
  assert.equal(m.steps[0].result.metrics, d.steps[0].result.metrics);
  // a failed explore keeps the step as it was
  const failed = await loadExploration({ path: ['2'], explore: async () => { throw new Error('x'); } });
  assert.deepEqual(failed, [null]);
  assert.equal(mergeExploration(d, failed).steps[0], d.steps[0]);
});

test('stage 3: the summary comes from POST /report/summary, or from POST /report on an older API', async (t) => {
  const { clearSummaryCache } = await import('./pathReport.js'); clearSummaryCache();
  t.mock.method(globalThis, 'fetch', async (url) => ({ ok: true, json: async () => ({ text: 'Wenn…', mode: 'llm', model: 'm' }) }));
  const s = await loadSummary({ path: ['2'], lang: 'de' });
  assert.equal(s.text, 'Wenn…');
  assert.equal(s.mode, 'llm');
  assert.match(globalThis.fetch.mock.calls[0].arguments[0], /\/report\/summary$/);
  assert.equal(JSON.parse(globalThis.fetch.mock.calls[0].arguments[1].body).language, 'de');
  // no /report/summary yet: take the worded summary from /report
  clearSummaryCache();
  globalThis.fetch.mock.mockImplementation(async (url) => (/summary$/.test(url) ? { ok: false, status: 404 }
    : { ok: true, json: async () => ({ sections: { summary: { text: 'If…', mode: 'template' }, validation: { test_evidence: [{ file: 'a', test: 'b' }] } } }) }));
  const old = await loadSummary({ path: ['2'] });
  assert.equal(old.text, 'If…');
  assert.equal(old.testEvidence.length, 1);
  // a server error rejects: the page keeps its own template
  clearSummaryCache();
  globalThis.fetch.mock.mockImplementation(async () => ({ ok: false, status: 500 }));
  await assert.rejects(loadSummary({ path: ['2'] }), /500/);
});

test('stage 2b: fix / surface / timing in parallel with the session conditions; a failing route gives null', async () => {
  const { loadAnalyses, fixTarget } = await import('./pathReport.js');
  const calls = [];
  const request = async (route, { body }) => { calls.push([route, body]); if (route === '/tree/timing_scan') throw new Error('The API returned 501.'); return { route }; };
  const a = await loadAnalyses({ path: ['2'], level: 'needs_financing', peer: '1', weather: ['recession'], request });
  assert.equal(a.fix.route, '/tree/smallest_change');
  assert.equal(a.surface.route, '/tree/surface');
  assert.equal(a.timing, null);
  assert.equal(calls.find(([r]) => r === '/tree/smallest_change')[1].target, 'no_funding_gap');
  assert.equal(calls.find(([r]) => r === '/tree/surface')[1].compare_to, '1');
  assert.deepEqual(calls[0][1].weather, ['recession']);
  assert.equal(fixTarget('holds'), null);
  const held = await loadAnalyses({ path: ['2'], level: 'holds', request: async (r) => ({ r }) });
  assert.equal(held.fix, null);
});

test('the worded summary is fetched once per (path, conditions, weather, language) in a session', async () => {
  const { loadSummary, clearSummaryCache } = await import('./pathReport.js');
  clearSummaryCache();
  let n = 0;
  const request = async (route, { body }) => { n++; return { text: `t-${body.language}`, mode: 'llm' }; };
  assert.equal((await loadSummary({ path: ['2'], lang: 'en', request })).text, 't-en');
  assert.equal((await loadSummary({ path: ['2'], lang: 'en', request })).text, 't-en');
  assert.equal(n, 1);
  await loadSummary({ path: ['2'], lang: 'de', request });
  await loadSummary({ path: ['2'], lang: 'en', weather: [{ type: 'scenario', level: 'pessimistic' }], request });
  await loadSummary({ path: ['2', '2.1'], lang: 'en', request });
  assert.equal(n, 4);
  const fail = async () => { throw new Error('The API returned 500.'); };
  await assert.rejects(loadSummary({ path: ['3'], lang: 'en', request: fail }), /500/); // failures are not cached
});
