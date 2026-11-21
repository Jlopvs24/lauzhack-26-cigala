import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildFromExpand, fetchPathReport } from './pathReport.js';

const load = (f) => JSON.parse(readFileSync(new URL(`../../../core/examples/${f}`, import.meta.url), 'utf8'));
const levels = { '': load('expand_alexia_root.json'), 2: load('expand_alexia_2.json') };
const expand = async (p) => levels[p.join('.')];

test('without POST /report the path report is built from expand with the report_data shape', async () => {
  const d = await buildFromExpand({ path: ['2'], expand });
  assert.equal(d.source, 'expand');
  assert.equal(d.steps.length, 1);
  assert.equal(d.steps[0].node_id, '2');
  assert.deepEqual(d.steps[0].alternatives.map((a) => a.node_id).sort(), ['1', '3']);
  assert.equal(d.leaf.plan_check.level, 'needs_financing');
  assert.equal(d.stress[0].weather, 'none');
  assert.equal(d.stress.length, 1 + (d.leaf.weather_resilience?.by_weather?.length || 0));
  assert.equal(d.leaf.monthly_surplus.length, d.steps[0].result.deterministic.cash.length - 1);
  assert.ok(d.limitations.some((x) => /not a forecast/.test(x)));
});

test('uses POST /report when it exists, falls back only on 404/405', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => ({ steps: [], leaf: {}, question: {} }) }));
  assert.equal((await fetchPathReport({ path: ['2'] })).source, 'report');
  globalThis.fetch.mock.mockImplementation(async () => ({ ok: false, status: 500 }));
  await assert.rejects(fetchPathReport({ path: ['2'] }), /500/);
});
