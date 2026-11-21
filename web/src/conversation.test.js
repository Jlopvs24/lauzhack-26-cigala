import test from 'node:test';
import assert from 'node:assert/strict';
import { askLumi } from './conversation.js';

test('history is kept: every turn carries the previous ones; voice notes use their transcript', async t => {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ answer: `A${calls.length}`, transcript: 'what if I share a flat', cost_usd: 0.001 }) };
  });
  let messages = [];
  for (const q of ['first?', 'second?']) {
    const { user, assistant } = await askLumi({ question: q, context: { node_id: '2', language: 'en' }, messages });
    messages = [...messages, user, assistant];
  }
  assert.deepEqual(messages.map(m => m.content), ['first?', 'A1', 'second?', 'A2']);
  assert.deepEqual(JSON.parse(calls[1].options.body).context.history.map(m => m.content), ['first?', 'A1']);
  const audio = new File([new Uint8Array(8)], 'voice-note.wav', { type: 'audio/wav' });
  const v = await askLumi({ audio, context: { language: 'es' }, messages });
  assert.equal(calls[2].url, '/api/voice/ask');
  assert.equal(calls[2].options.body.get('language'), 'es');
  assert.equal(v.user.content, 'what if I share a flat');
  assert.equal(v.user.voice, true);
});

test('ungrounded answers are rejected', async t => {
  t.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => ({ answer: 'x', grounding: { grounded: false } }) }));
  await assert.rejects(askLumi({ question: 'q', context: {} }), /could not be verified/);
});
