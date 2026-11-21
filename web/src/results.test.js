import test from 'node:test';
import assert from 'node:assert/strict';
import { bandGeometry, strongestSensitivity, assumptionOverrides, healthFraction } from './results.js';

test('chart spans losses, profits and flat zero without invalid coordinates', () => {
  for (const bands of [{ p10: [-100, -200], p50: [0, 0], p90: [100, 200] },
    { p10: [0, 0], p50: [0, 0], p90: [0, 0] }]) {
    const chart = bandGeometry(bands);
    assert.ok(chart.low < chart.high);
    assert.ok(Number.isFinite(chart.zeroY));
    assert.doesNotMatch(chart.area + chart.median, /NaN|Infinity/);
  }
  assert.equal(bandGeometry({ p10: [0, 1], p50: [0], p90: [0, 2] }), null);
  assert.equal(bandGeometry({ p10: [0, 3], p50: [0, 2], p90: [0, 4] }), null);
  assert.equal(bandGeometry({}), null);
});
test('sensitivity ranks by absolute effect, including negative effects', () => {
  const items = [{ delta_final_net_worth: 5 }, { delta_final_net_worth: -20 }];
  assert.equal(strongestSensitivity(items), items[1]);
  assert.equal(strongestSensitivity(), null);
  assert.equal(strongestSensitivity(null), null);
});
test('health displays the mock and core scales without multiplying a core score by 100', () => {
  assert.equal(healthFraction({ score: 0.5, components: { liquidity: 1 } }), 0.5);
  assert.equal(healthFraction({ score: 49.5, components: { liquidity: { score: 0 } } }), 0.495);
  assert.equal(healthFraction({ score: 0.5, components: { liquidity: { score: 0 } } }), 0.005);
  assert.equal(healthFraction({}), null);
});
test('assumption edits preserve decimals; blank and invalid probabilities cannot be applied', () => {
  const assumptions = [{ id: 'a', param: 'annual_return', editable: true }, { id: 'fixed', editable: false }];
  assert.deepEqual(assumptionOverrides(assumptions, { a: '-0.05' }), [{ id: 'a', value: -0.05 }]);
  for (const a of ['', ' ', 'Infinity', 'oops']) assert.throws(() => assumptionOverrides(assumptions, { a }));
  assert.throws(() => assumptionOverrides([{ id: 'p', param: 'monthly_job_loss_prob', editable: true }], { p: '1.1' }));
});
