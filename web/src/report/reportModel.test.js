import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildFromLevels } from './pathReport.js';
import { chf, compact, compareLevels, constraintRows, fmtVal, heroTiles, oneLiner, plainTemplate, signedChf, stressRows, timeSeries, tornadoRows, whatIfCards } from './reportModel.js';
import { RI } from './reportI18n.js';

const load = (f) => JSON.parse(readFileSync(new URL(`../../../core/examples/${f}`, import.meta.url), 'utf8'));
const data = buildFromLevels([load('expand_alexia_root.json'), load('expand_alexia_2.json')], { path: ['2'] });
const tr = (n) => ({ label: n.label, desc: n.description || '' });

test('formatting: Swiss thousands, real minus sign, compact axes, unit-aware values', () => {
  assert.equal(chf(121727.55), 'CHF 121’728');
  assert.equal(chf(-18835.02), '−CHF 18’835');
  assert.equal(signedChf(-18789.11), '−CHF 18’789');
  assert.equal(signedChf(0.2), '±CHF 0');
  assert.equal(compact(-3820), '−3.8k');
  assert.equal(compact(120000), '120k');
  assert.equal(fmtVal(4844.64, 'CHF/month'), 'CHF 4’845/month');
  assert.equal(fmtVal(0.01, '1/year'), '1%');
  assert.equal(fmtVal(1.2, 'multiplier'), '×1.2');
});

test('hero: the if-then line and the four key numbers come from the leaf, feasibility first', () => {
  assert.match(oneLiner(data, 'en', tr), /^If you take this path, then under these assumptions cash runs short from month 7 .*CHF 110’198/);
  assert.match(oneLiner(data, 'de', tr), /ab Monat 7/);
  const t = heroTiles(data, 'en');
  assert.deepEqual(t.map((x) => x.key), ['plan', 'gap', 'nw', 'goals']);
  assert.equal(t[0].value, 'Needs financing');
  assert.equal(t[0].tone, 'bad');
  assert.equal(t[1].value, 'CHF 18’835');
  assert.match(t[1].sub, /from month 7/);
  assert.equal(t[2].value, 'CHF 110’198');
  assert.equal(t[3].value, '2 of 2');
  assert.ok(!/best|will |expected/i.test(oneLiner(data, 'en', tr) + plainTemplate(data, 'en', tr)));
});

test('what would have to be true: broken plan reads broken, break-even threshold, goals, timing', () => {
  const cards = whatIfCards(data.steps[0], 'en', tr);
  const by = Object.fromEntries(cards.map((c) => [c.key, c]));
  assert.equal(by.shock.tone, 'bad');
  assert.match(by.shock.text, /month 7/);
  assert.equal(by.break.big, 'CHF 4’845/month');
  assert.match(by.break.text, /“Start working”/);
  assert.equal(by.break.more.length, 2);
  assert.equal(by.goal.tone, 'good');
  assert.equal(by.timing.big, '−CHF 18’789');
  assert.match(by.timing.text, /12 months later; short from month 14/);
  assert.equal(whatIfCards({ result: {} }, 'en', tr).length, 0);
});

test('charts data: tornado sorted by swing, series with the chosen path last, levels with siblings', () => {
  const rows = tornadoRows(data.steps[0]);
  assert.ok(rows.length >= 3);
  assert.ok(rows.every((r, i) => i === 0 || r.swing <= rows[i - 1].swing));
  assert.ok(Number.isFinite(rows[0].base));
  const s = timeSeries(data, 'cash');
  assert.equal(s.at(-1).chosen, true);
  assert.equal(s.length, 3);
  assert.equal(timeSeries(data, 'nw').at(-1).values.at(-1), data.leaf.peers.find((p) => p.chosen).net_worth.at(-1));
  const lv = compareLevels(data);
  assert.equal(lv[0].rows.length, 3);
  assert.equal(lv[0].rows[0].chosen, true);
});

test('does it hold: stress rows and constraints with signed, bounded margins', () => {
  const st = stressRows(data, 'fr');
  assert.equal(st[0].name, 'Comme prévu');
  assert.equal(st[0].holds, false);
  assert.equal(st[0].short, 7);
  const c = constraintRows(data.leaf.constraints, 'en');
  const gap = c.find((x) => x.name === 'no_funding_gap');
  assert.equal(gap.passed, false);
  assert.equal(gap.ratio, -1);
  assert.match(gap.sub, /from month 7/);
  const debt = c.find((x) => x.name === 'debt_service_limit');
  assert.match(debt.label, /33%/);
  assert.ok(c.every((x) => x.ratio >= -1 && x.ratio <= 1));
});

test('every language has every string of the English report', () => {
  const shape = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, Array.isArray(v) ? `array${v.length}` : typeof v === 'object' ? shape(v) : typeof v]));
  for (const lang of ['es', 'fr', 'de']) assert.deepEqual(shape(RI[lang]), shape(RI.en), lang);
});
