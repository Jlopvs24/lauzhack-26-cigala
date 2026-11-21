import test from 'node:test';
import assert from 'node:assert/strict';

function fakeStorage(init) {
  const m = new Map(Object.entries(init));
  return { get length() { return m.size; }, key: (i) => [...m.keys()][i] ?? null, getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), keys: () => [...m.keys()].sort() };
}

test('#118: a reload clears the chat, pins, conditions and Live consent, keeps the summary cache', async () => {
  const { freshStart } = await import('./freshStart.js');
  const s = fakeStorage({ 'cigala.chat.v1': '[1]', 'cigala.compare.v1': '[2]', 'cigala.personal.v1': '[3]',
    'cigala.live.consent.v1': '1', 'cigala.summary.v1': '{}', 'other.app': 'x' });
  assert.deepEqual(freshStart(s).sort(), ['cigala.chat.v1', 'cigala.compare.v1', 'cigala.live.consent.v1', 'cigala.personal.v1']);
  assert.deepEqual(s.keys(), ['cigala.summary.v1', 'other.app']);
  assert.deepEqual(freshStart(null), []);
  assert.deepEqual(freshStart({ get length() { throw new Error('blocked'); } }), []);
});
