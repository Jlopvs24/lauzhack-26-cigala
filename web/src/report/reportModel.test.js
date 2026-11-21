import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildFromLevels } from './pathReport.js';
import { chf, compact, compareLevels, constraintRows, fmtVal, heroTiles, oneLiner, plainTemplate, signedChf, stressRows, timeSeries, tornadoRows, whatIfCards } from './reportModel.js';
import { RI } from './reportI18n.js';

const load = (f) => JSON.parse(readFileSync(new URL(`../../../core/examples/${f}`, import.meta.url), 'utf8'));
const data = buildFromLevels([load('expand_alexia_root.json'), load('expand_alexia_2.json')], { path: ['2'] });
const tr = (n) => ({ label: n.label, desc: n.description || '' });
// expected values come from the engine fixture, so a recalibrated engine does not break these tests
const leaf = data.steps[0].summary, ex = data.steps[0].result.exploration;
const m1 = leaf.first_negative_month + 1;

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
  assert.equal(oneLiner(data, 'en', tr), `If you take this path, then under these assumptions cash runs short from month ${m1} and net worth after 10 years is ${chf(leaf.final_net_worth_real)} in today’s prices.`);
  assert.match(oneLiner(data, 'de', tr), new RegExp(`ab Monat ${m1} `));
  const t = heroTiles(data, 'en');
  assert.deepEqual(t.map((x) => x.key), ['plan', 'gap', 'nw', 'goals']);
  assert.equal(t[0].value, 'Needs financing');
  assert.equal(t[0].tone, 'bad');
  assert.equal(t[1].value, chf(Math.abs(leaf.min_cash)));
  assert.match(t[1].sub, new RegExp(`from month ${m1} `));
  assert.equal(t[2].value, chf(leaf.final_net_worth_real));
  assert.equal(t[3].value, '2 of 2');
  assert.ok(!/best|will |expected/i.test(oneLiner(data, 'en', tr) + plainTemplate(data, 'en', tr)));
});

test('what would have to be true: broken plan reads broken, break-even threshold, goals, timing', () => {
  const cards = whatIfCards(data.steps[0], 'en', tr);
  const by = Object.fromEntries(cards.map((c) => [c.key, c]));
  assert.equal(by.shock.tone, 'bad');
  assert.match(by.shock.text, new RegExp(`month ${m1},`));
  const th = ex.break_even.find((b) => b.salary_threshold?.status === 'threshold_found').salary_threshold;
  assert.equal(by.break.big, fmtVal(th.value, th.unit));
  assert.match(by.break.big, /^CHF \d+’\d{3}\/month$/);
  assert.match(by.break.text, /“Start working”/);
  assert.equal(by.break.more.length, 2);
  assert.equal(by.goal.tone, 'good');
  assert.equal(by.timing.big, signedChf(ex.timing[0].delta_final_net_worth));
  assert.match(by.timing.text, new RegExp(`12 months later; short from month ${ex.timing[0].first_negative_month + 1}\\.`));
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
  assert.match(gap.sub, new RegExp(`from month ${m1},`));
  const debt = c.find((x) => x.name === 'debt_service_limit');
  assert.match(debt.label, /33%/);
  assert.ok(c.every((x) => x.ratio >= -1 && x.ratio <= 1));
});

test('every language has every string of the English report', () => {
  const shape = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, Array.isArray(v) ? `array${v.length}` : typeof v === 'object' ? shape(v) : typeof v]));
  for (const lang of ['es', 'fr', 'de']) assert.deepEqual(shape(RI[lang]), shape(RI.en), lang);
});

test('tax residence: one line per stretch, abroad with its assumed rate, Lausanne fallback flagged', async () => {
  const { taxSegments } = await import('./reportModel.js');
  const segs = [
    { from_month: 0, to_month: 36, taxed: true, city: null, canton: null, household: 'single', country: 'abroad', source: 'assumption:tax_abroad_rate', fallback: false },
    { from_month: 36, to_month: 120, taxed: true, city: 'Zurich', canton: 'ZH', household: 'couple', country: 'CH', source: 'ESTV 2026', matched: 'city', fallback: false },
  ];
  const t = taxSegments(segs, 'en', [{ id: 'AS-tax-abroad-rate', value: 0.15, verified: false }]);
  assert.deepEqual(t.map((x) => x.unverified), [true, false]);
  assert.deepEqual(t.map((x) => [x.place, x.household, x.months, x.fallback]), [
    ['Abroad: one assumed rate of 15%', 'single', 'months 1–36', false],
    ['Zurich (ZH): official ESTV 2026 table', 'married, one earner', 'months 37–120', false],
  ]);
  const fb = taxSegments([{ from_month: 0, to_month: 120, taxed: true, city: 'Lausanne', canton: 'VD', household: 'single', country: 'CH', fallback: true }], 'de');
  assert.equal(fb[0].fallback, true);
  assert.match(fb[0].months, /Monate 1–120/);
  assert.match(taxSegments([{ from_month: 0, to_month: 120, taxed: false, reason: 'take_home' }], 'fr')[0].place, /Non imposé/);
  assert.deepEqual(taxSegments(undefined), []);
});

test('pillar 3a card: three options split into liquid and locked, caveat and goal-seek; absent field draws nothing', async () => {
  const { pillar3a } = await import('./reportModel.js');
  const p = { status: 'evaluated', monthly_amount: 604.83, annual_cap: 7258, options: [
    { option: 'pay_into_3a', final_net_worth: 151819.73, final_liquid: 75520.86, final_pillar_3a: 76298.87, min_cash: 8319.98, tax_saved_by_3a: 22745.09 },
    { option: 'keep_in_cash', final_net_worth: 125604.88, final_liquid: 125604.88, final_pillar_3a: 0, min_cash: 8736.47, tax_saved_by_3a: 0 },
    { option: 'invest', final_net_worth: 141899.8, final_liquid: 141899.8, final_pillar_3a: 0, min_cash: 8131.64, tax_saved_by_3a: 0 }],
    highest_final_net_worth: 'pay_into_3a', max_monthly_3a_keeping_goals: { status: 'full_amount_keeps_goals', value: 604.83 } };
  const c = pillar3a({ result: { exploration: { pillar_3a: p } } }, 'en');
  assert.deepEqual(c.rows.map((r) => r.key), ['keep_in_cash', 'pay_into_3a', 'invest']);
  assert.deepEqual(c.rows.map((r) => r.label), ['Kept in cash', 'Paid into pillar 3a', 'Invested']);
  assert.equal(c.rows[1].locked, 76298.87);
  assert.match(c.lead, /^If CHF 605 a month \(this branch’s cap, CHF 7’258 a year\).*then under these assumptions/);
  assert.equal(c.caveat, 'Paying into 3a saves CHF 22’745 of income tax, but only CHF 75’521 stays liquid: the CHF 76’299 in 3a is locked until retirement (early withdrawal only for a home, self-employment or leaving Switzerland).');
  assert.equal(c.seek, 'Paying the full CHF 605 a month still meets every dated goal.');
  assert.ok(!/best|recommend/i.test(c.lead + c.caveat + c.seek));
  assert.match(pillar3a({ result: { exploration: { pillar_3a: p } } }, 'de').caveat, /bis zur Pensionierung gebunden/);
  assert.equal(pillar3a({ result: { exploration: { pillar_3a: { ...p, max_monthly_3a_keeping_goals: { status: 'goals_already_missed', value: null } } } } }, 'es').seek,
    'Los objetivos con fecha ya se incumplen sin 3a, así que ninguna aportación los mantiene.');
  assert.equal(pillar3a({ result: { exploration: { pillar_3a: { status: 'no_earned_income' } } } }, 'fr').rows.length, 0);
  assert.equal(pillar3a({ result: { exploration: {} } }), null);
  assert.equal(pillar3a(undefined), null);
});
