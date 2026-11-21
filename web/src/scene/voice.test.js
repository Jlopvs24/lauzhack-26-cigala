import test from 'node:test';
import assert from 'node:assert/strict';
import { splitSentences, pickVoice } from './voice.js';
import { openingFor, storyFor } from './narration.js';

test('sentences split at .!? + space, never inside numbers', () => {
  assert.deepEqual(splitSentences('Negotiate a 5% raise. Tightest buffer: 2.9 months! Then? Done'),
    ['Negotiate a 5% raise.', 'Tightest buffer: 2.9 months!', 'Then?', 'Done']);
  assert.deepEqual(splitSentences(''), []);
});

test('a German voice is picked for de, never an English one', () => {
  const vs = [{ lang: 'en-US', localService: true }, { lang: 'de-AT', localService: true }, { lang: 'de-DE', localService: false, name: 'Google Deutsch' }];
  assert.equal(pickVoice(vs, 'de').lang, 'de-DE');
  assert.equal(pickVoice([{ lang: 'de_CH', localService: true }], 'de').lang, 'de_CH');
  assert.equal(pickVoice([{ lang: 'en-GB' }], 'de'), null);
});

test("a child's prefetched opening is exactly how its narration starts", () => {
  const child = { node_id: '1', parent_id: '0', label: 'Start working', description: 'Take a job after the degree', status: 'chosen',
    result: { metrics: {}, health: { score: 60 } } };
  for (const lang of ['en', 'es', 'fr', 'de']) {
    const open = openingFor(child, lang);
    const story = storyFor({ current: '1', nodes: [child] }, lang);
    const first2 = splitSentences(open).slice(0, 2).join(' ');
    assert.ok(story.startsWith(first2), `${lang}: "${story.slice(0, 60)}" vs "${first2}"`);
  }
});

test('mouth level: silence is 0, a loud wave saturates at 1', async () => {
  const { levelFromSamples } = await import('./voice.js');
  assert.equal(levelFromSamples(new Uint8Array(64).fill(128)), 0);
  const loud = Uint8Array.from({ length: 64 }, (_, i) => (i % 2 ? 255 : 0));
  assert.equal(levelFromSamples(loud), 1);
  const soft = Uint8Array.from({ length: 64 }, (_, i) => (i % 2 ? 138 : 118));
  assert.ok(levelFromSamples(soft) > 0.2 && levelFromSamples(soft) < 0.6);
});
