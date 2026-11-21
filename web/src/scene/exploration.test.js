import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { explorationSections } from './exploration.js';
import { renderReport } from './report.js';

const example = JSON.parse(readFileSync(new URL('../../../core/examples/expand_alexia_2.json', import.meta.url), 'utf8'));
const cur = example.nodes.find((n) => n.node_id === example.current);
const ex = cur.result.exploration;

test('a plan that is already broken reads as broken, not as a CHF 0 threshold', () => {
  const html = explorationSections(ex, { lang: 'en', metrics: cur.result.metrics });
  assert.match(html, /Cash already runs short in this scenario<\/b> from month 7/);
  assert.doesNotMatch(html, /absorbs a surprise cost of up to <b>CHF 0/);
});

test('levers offer recompute buttons; thresholds and timing become sentences', () => {
  const html = explorationSections(ex, { lang: 'en', metrics: cur.result.metrics });
  assert.match(html, /data-lever="AS-alexia-master-salary" data-value="5600"/);
  assert.match(html, /Both end level if net salary after the master's is <b>4’845 CHF\/month<\/b>/);
  assert.match(html, /Deciding <b>12 months later<\/b>/);
  assert.match(html, /Real wage growth.*\(now 1%\): at 0% /);
  assert.match(html, /Emergency savings<\/b>: reached without extra income/);
});

test('null values show their status in words, in every language', () => {
  const nulls = { break_even: [{ label: 'Start working', delta_final_net_worth: -10, sustained_crossover_month: null,
    salary_threshold: { assumption_id: 'X', status: 'non_monotone', value: null } }],
    goal_seek: [{ goal: 'Car', status: 'not_reached_within_bounds', value: null }] };
  assert.match(explorationSections(nulls, { lang: 'en' }), /no single threshold.*not reached within the tested range/s);
  assert.match(explorationSections(nulls, { lang: 'de' }), /keine eindeutige Schwelle/);
  assert.doesNotMatch(explorationSections(nulls, { lang: 'es' }), /null|NaN|undefined/);
});

test('the real expand result renders: exploration first, no Monte Carlo when the lens is off', () => {
  const html = renderReport({ data: example, lang: 'en', ui: { today: 'Today', branch: 'Branch' }, tr: (n) => ({ label: n.label, desc: n.description || '' }), lens: false });
  assert.ok(html.indexOf('What would have to be true') < html.indexOf('Cash and net worth, month by month'));
  assert.doesNotMatch(html, /NaN|undefined/);
  assert.doesNotMatch(html, /Median net worth/);
});
