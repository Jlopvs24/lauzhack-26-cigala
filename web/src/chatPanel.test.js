import assert from 'node:assert/strict';
import test from 'node:test';
import { API_TURNS, MAX_MESSAGES, createHistory } from './chatHistory.js';
import { PANEL_MAX, PANEL_MIN, PHONE_MAX, announcePanel, insets, panelLayout } from './chatPanel.js';

function memoryStorage() {
  const data = new Map();
  return { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)),
    removeItem: (k) => data.delete(k), data };
}

test('history survives a new panel instance (node / language changes, reloads)', () => {
  const storage = memoryStorage();
  const a = createHistory({ storage });
  a.append('user', 'Why does the master need financing?');
  a.append('assistant', 'Under these assumptions cash goes below zero in month 7.', { mode: 'llm', node_id: '2' });
  const b = createHistory({ storage });
  assert.equal(b.all().length, 2);
  assert.equal(b.all()[1].meta.node_id, '2');
  assert.ok(b.persistent);
});

test('only role and content are sent to the API, at most the last turns', () => {
  const h = createHistory({ storage: memoryStorage() });
  for (let i = 0; i < 15; i += 1) h.append(i % 2 ? 'assistant' : 'user', `m${i}`, { cost_usd: 0.001 });
  const sent = h.forApi();
  assert.equal(sent.length, API_TURNS);
  assert.deepEqual(Object.keys(sent[0]).sort(), ['content', 'role']);
  assert.equal(sent.at(-1).content, 'm14');
});

test('history is capped, ignores junk and works without storage', () => {
  const storage = memoryStorage();
  storage.setItem('cigala.chat.v1', JSON.stringify([{ role: 'system', content: 'x' }, { role: 'user', content: '' }, 7,
    { role: 'user', content: 'kept' }]));
  const h = createHistory({ storage });
  assert.deepEqual(h.all().map((m) => m.content), ['kept']);
  for (let i = 0; i < MAX_MESSAGES + 5; i += 1) h.append('user', `q${i}`);
  assert.equal(h.all().length, MAX_MESSAGES);
  const blocked = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); }, removeItem() {} };
  const mem = createHistory({ storage: blocked });
  mem.append('user', 'still works');
  assert.equal(mem.all().length, 1);
  assert.equal(mem.persistent, false);
});

test('subscribers see appends and clear', () => {
  const h = createHistory({ storage: memoryStorage() });
  const seen = [];
  const off = h.subscribe((list) => seen.push(list.length));
  h.append('user', 'a'); h.clear(); off(); h.append('user', 'b');
  assert.deepEqual(seen, [1, 0]);
});

test('layout: right side panel on desktop, bottom sheet on phones', () => {
  assert.deepEqual(panelLayout(1440, 900), { side: 'right', width: 432, height: 900 });
  assert.equal(panelLayout(1000, 800).width, PANEL_MIN);
  assert.equal(panelLayout(2560, 1400).width, PANEL_MAX);
  const phone = panelLayout(390, 844);
  assert.equal(phone.side, 'bottom');
  assert.equal(phone.width, 390);
  assert.ok(phone.height > 400 && phone.height < 844);
  assert.equal(panelLayout(PHONE_MAX, 800).side, 'right');
  assert.deepEqual(insets(panelLayout(1440, 900), true), { right: 432, bottom: 0 });
  assert.deepEqual(insets(phone, true), { right: 0, bottom: phone.height });
  assert.deepEqual(insets(phone, false), { right: 0, bottom: 0 });
});

test('announcePanel dispatches the contract events and sets the CSS vars', () => {
  const target = new EventTarget();
  const vars = {};
  const root = { style: { setProperty: (k, v) => { vars[k] = v; } } };
  const got = [];
  target.addEventListener('panel:open', (e) => got.push(['open', e.detail]));
  target.addEventListener('panel:close', (e) => got.push(['close', e.detail]));
  const layout = panelLayout(1440, 900);
  announcePanel(true, layout, { target, root });
  assert.deepEqual(vars, { '--chat-panel-w': '432px', '--chat-panel-h': '0px' });
  announcePanel(false, layout, { target, root });
  assert.deepEqual(vars, { '--chat-panel-w': '0px', '--chat-panel-h': '0px' });
  assert.deepEqual(got, [['open', { side: 'right', width: 432, height: 900 }], ['close', { side: 'right', width: 0, height: 0 }]]);
});
