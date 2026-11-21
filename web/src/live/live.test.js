import test from 'node:test';
import assert from 'node:assert/strict';
import { downsampleToInt16, int16ToFloat32, joinCaption, levelOf } from './pcm.js';
import { createLiveSession, wsUrl } from './liveSession.js';

test('downsample 48 kHz float to 16 kHz int16', () => {
  const x = new Float32Array(480).fill(0.5);
  const y = downsampleToInt16(x, 48000);
  assert.equal(y.length, 160);
  assert.ok(Math.abs(y[10] - 16383) <= 1);
  assert.equal(downsampleToInt16(new Float32Array([2, -2]), 16000)[1], -32768); // clipped
});

test('int16 bytes to float and level', () => {
  const buf = new ArrayBuffer(4);
  new DataView(buf).setInt16(0, 16384, true); new DataView(buf).setInt16(2, -32768, true);
  const f = int16ToFloat32(buf);
  assert.deepEqual([...f], [0.5, -1]);
  assert.equal(levelOf(new Float32Array(10)), 0);
  assert.equal(levelOf(new Float32Array(10).fill(1)), 1);
});

test('captions join without doubled spaces', () => {
  assert.equal(joinCaption(joinCaption('', ' If you'), ' take'), 'If you take');
  assert.equal(joinCaption('option 2', ', then'), 'option 2, then');
  assert.equal(joinCaption('Hello', 'there'), 'Hello there');
});

test('ws url from the API base', () => {
  assert.equal(wsUrl('/api', '/live/ws?token=a', 'http://127.0.0.1:5175/x'), 'ws://127.0.0.1:5175/api/live/ws?token=a');
  assert.equal(wsUrl('https://h.example/api', '/live/ws?token=a'), 'wss://h.example/api/live/ws?token=a');
});

class FakeWS {
  static last = null;
  constructor(url) { this.url = url; this.sent = []; this.readyState = 1; FakeWS.last = this; }
  send(m) { this.sent.push(m); }
  close() { this.readyState = 3; }
  push(m) { this.onmessage({ data: typeof m === 'string' ? m : JSON.stringify(m) }); }
}

const fetchOk = (body) => async (url, opts) => { fetchOk.calls.push([url, opts]); return { ok: true, json: async () => body }; };
fetchOk.calls = [];

test('session: token, ready, captions, tool, turn, end (no audio)', async () => {
  const events = [];
  const s = createLiveSession({ context: { node_id: '2', path: ['2'] }, lang: 'es', audio: false, base: 'http://api',
    fetchImpl: fetchOk({ available: true, ws_path: '/live/ws?token=t1' }), WebSocketImpl: FakeWS,
    on: { state: (st) => events.push(['state', st]), turn: (t) => events.push(['turn', t]), tool: (t) => events.push(['tool', t.name]),
      ended: (r) => events.push(['ended', r]) } });
  await s.start();
  const [url, opts] = fetchOk.calls.at(-1);
  assert.equal(url, 'http://api/live/token');
  assert.equal(JSON.parse(opts.body).context.language, 'es');
  const ws = FakeWS.last;
  assert.equal(ws.url, 'ws://api/live/ws?token=t1');
  ws.push({ type: 'ready', model: 'm' });
  assert.equal(s.state, 'live');
  assert.ok(s.sendText('¿Qué la arreglaría?'));
  assert.deepEqual(JSON.parse(ws.sent.at(-1)), { type: 'text', text: '¿Qué la arreglaría?' });
  ws.push({ type: 'tool', name: 'what_would_fix_it', args: { node_id: '2' }, ms: 30, ok: true });
  ws.push({ type: 'caption', role: 'model', text: 'Si tomas' });
  ws.push({ type: 'caption', role: 'model', text: ' la opción 2' });
  ws.push({ type: 'turn_complete', grounding: { grounded: true } });
  const turn = events.find((e) => e[0] === 'turn')[1];
  assert.equal(turn.user, '¿Qué la arreglaría?');
  assert.equal(turn.model, 'Si tomas la opción 2');
  assert.equal(turn.tools[0].name, 'what_would_fix_it');
  s.sendContext({ node_id: '1' });
  assert.equal(JSON.parse(ws.sent.at(-1)).type, 'context');
  s.end();
  assert.equal(JSON.parse(ws.sent.at(-1)).type, 'end');
  assert.deepEqual(events.at(-1), ['ended', 'user_ended']);
  assert.equal(s.state, 'ended');
});

test('session: unavailable token fails cleanly with the reason', async () => {
  const errors = [];
  const s = createLiveSession({ audio: false, base: 'http://api', fetchImpl: fetchOk({ available: false, reason: 'budget' }),
    WebSocketImpl: FakeWS, on: { error: (code) => errors.push(code) } });
  await s.start();
  assert.deepEqual(errors, ['budget']);
  assert.equal(s.state, 'error');
});

test('session: server end reason is reported', async () => {
  let reason = null;
  const s = createLiveSession({ audio: false, base: 'http://api', fetchImpl: fetchOk({ available: true, ws_path: '/live/ws?token=x' }),
    WebSocketImpl: FakeWS, on: { ended: (r) => { reason = r; } } });
  await s.start();
  FakeWS.last.push({ type: 'ended', reason: 'idle' });
  assert.equal(reason, 'idle');
});

test('#112: a server error before the end is shown, not a bare "stopped"', async () => {
  const states = [];
  const s = createLiveSession({ audio: false, base: 'http://api', fetchImpl: fetchOk({ available: true, ws_path: '/live/ws?token=e' }),
    WebSocketImpl: FakeWS, on: { state: (st, info) => states.push([st, info]) } });
  const err = console.error; console.error = () => {};
  try {
    await s.start();
    FakeWS.last.push({ type: 'error', message: 'Live setup failed. models/x is not found for API version v1beta' });
    FakeWS.last.push({ type: 'ended', reason: 'error' });
  } finally { console.error = err; }
  assert.equal(s.state, 'error');
  const [, info] = states.find(([st]) => st === 'error');
  assert.equal(info.code, 'server');
  assert.match(info.message, /not found for API version/);
});

test('#112: an abnormal socket close says its code; a normal end stays quiet', async () => {
  const err = console.error; console.error = () => {};
  try {
    const a = createLiveSession({ audio: false, base: 'http://api', fetchImpl: fetchOk({ available: true, ws_path: '/live/ws?token=c' }), WebSocketImpl: FakeWS });
    await a.start();
    FakeWS.last.onclose({ code: 1011, reason: 'internal error' });
    assert.equal(a.state, 'error');
    const b = createLiveSession({ audio: false, base: 'http://api', fetchImpl: fetchOk({ available: true, ws_path: '/live/ws?token=d' }), WebSocketImpl: FakeWS });
    await b.start();
    FakeWS.last.push({ type: 'ended', reason: 'idle' });
    assert.equal(b.state, 'ended');
  } finally { console.error = err; }
});
