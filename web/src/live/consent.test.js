import test from 'node:test';
import assert from 'node:assert/strict';
import { createConsent, CONSENT_KEY } from './consent.js';

const store = () => { const m = new Map(); return { m, getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) }; };

test('#103: Live asks before connecting and remembers the answer for the session', () => {
  const s = store(), c = createConsent(s);
  assert.equal(c.given(), false);
  c.give();
  assert.equal(c.given(), true);
  assert.equal(s.m.get(CONSENT_KEY), '1');
  assert.equal(createConsent(s).given(), true); // same session storage: no second prompt
  c.reset();
  assert.equal(c.given(), false);
});

test('consent still holds for the page when storage is blocked', () => {
  const broken = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); }, removeItem() { throw new Error('blocked'); } };
  const c = createConsent(broken);
  assert.equal(c.given(), false);
  c.give();
  assert.equal(c.given(), true);
});
