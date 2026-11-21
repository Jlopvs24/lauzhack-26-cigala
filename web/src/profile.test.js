import test from 'node:test';
import assert from 'node:assert/strict';
import { profileFromForm } from './profile.js';

const profile = { display_name: 'Alexia', city: 'Lausanne', age: 20, cash: 8000,
  monthly_net_income: 1200, monthly_rent: 900, monthly_other_expenses: 600,
  assets: [{ type: 'investment', value: 50 }], provenance: { cash: { source: 'document', confidence: 0.8 } } };
test('reviewed fields preserve extracted provenance; edits get their own provenance', () => {
  const edited = profileFromForm(profile, { ...profile, monthly_rent: '700', cash: '-10.50' }, ['monthly_rent', 'cash']);
  assert.equal(edited.monthly_rent, 700);
  assert.equal(edited.cash, -10.5);
  assert.equal(edited.provenance.cash.source, 'questionnaire');
  assert.equal(profileFromForm(profile, profile).provenance.cash.source, 'document');
  assert.deepEqual(edited.assets, profile.assets);
  assert.equal(profile.cash, 8000);
});
test('reject empty, non-finite and invalid fields before simulation', () => {
  assert.throws(() => profileFromForm({ ...profile, currency: 'EUR' }, profile), /CHF/);
  for (const change of [{ age: 2.5 }, { age: 121 }, { monthly_rent: -1 }, { cash: 'Infinity' }, { cash: '' }, { display_name: ' ' }]) {
    assert.throws(() => profileFromForm(profile, { ...profile, ...change }));
  }
});
