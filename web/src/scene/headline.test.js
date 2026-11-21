import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { cardHeadline, planCheck, planCheckHTML } from './headline.js';
import { storyFor } from './narration.js';

const ex = JSON.parse(readFileSync(new URL('../../../core/examples/expand_alexia_2.json', import.meta.url), 'utf8'));
const node = (id) => ex.nodes.find((n) => n.node_id === id);

test('cards: slot A says whether it holds, slot B what it trades, in the UI language', () => {
  const master = cardHeadline(node('2').result, 'en');
  assert.equal(master.a.kind, 'funding_gap');
  assert.match(master.a.text, /^Funding gap CHF 18’553 from month 7$/);
  const es = cardHeadline(node('2').result, 'es');
  assert.match(es.a.text, /^Falta financiación de CHF 18’553 desde el mes 7$/);
  for (const n of ex.nodes.filter((x) => x.result?.headline?.slot_b)) {
    const h = cardHeadline(n.result, 'de');
    assert.ok(h.b.text && !/undefined|NaN/.test(h.b.text + h.b.vs), n.node_id);
  }
});

test('plan check comes first: a funding gap reads "needs financing" whatever the score', () => {
  const r = node('2').result;
  assert.equal(planCheck(r, 'en').label, 'Needs financing');
  const html = planCheckHTML(r, 'en');
  assert.match(html, /Needs financing/);
  assert.match(html, /✕/);
  assert.match(storyFor(ex, 'en'), /Plan check: needs financing\./);
  assert.doesNotMatch(storyFor(ex, 'en'), /out of 100/);
});

test('works before core-1.2 (no headline / plan_check): computed from metrics with the same rule', () => {
  const old = { metrics: { first_negative_month: 6, min_cash: -18835 }, health: { score: 80 } };
  assert.match(cardHeadline(old, 'en').a.text, /Funding gap CHF 18’835 from month 7/);
  assert.equal(planCheck(old, 'en').level, 'needs_financing');
});

test('#103: under a macro outlook slot B says how much it moves the card, in every language', () => {
  const r = { headline: { slot_a: null, slot_b: { metric: 'final_net_worth_real', unit: 'CHF', value: 89787, vs_parent: 5, vs_neutral: -23921 } } };
  assert.match(cardHeadline(r, 'en').b.vs, /^−CHF 23’921 vs the neutral outlook$/);
  assert.match(cardHeadline(r, 'es').b.vs, /perspectiva neutral/);
  assert.match(cardHeadline(r, 'fr').b.vs, /perspective neutre/);
  assert.match(cardHeadline(r, 'de').b.vs, /neutralen Perspektive/);
  const same = { headline: { slot_b: { ...r.headline.slot_b, vs_neutral: 0.2 } } };
  assert.equal(cardHeadline(same, 'en').b.vs, 'same as the neutral outlook');
});
