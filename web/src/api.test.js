import test from 'node:test';
import assert from 'node:assert/strict';
import { apiRequest } from './api.js';

test('JSON and multipart requests preserve the backend contracts and reject service failures', async t => {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ answer: 'test' }) };
  });
  await apiRequest('/agent/ask', { body: { question: 'Why?', context: { path: ['2'] } } });
  assert.equal(calls[0].url, '/api/agent/ask');
  assert.deepEqual(JSON.parse(calls[0].options.body).context.path, ['2']);
  const form = new FormData(); form.append('text', 'fictional profile');
  await apiRequest('/profiles/extract', { body: form });
  assert.equal(calls[1].options.body, form);
  assert.equal(calls[1].options.headers, undefined);
  globalThis.fetch.mock.mockImplementation(async () => ({ ok: false, status: 503 }));
  await assert.rejects(apiRequest('/voice/ask', { body: form }), /try text input/);
});
