import test from 'node:test';
import assert from 'node:assert/strict';
import { createNarrator, storyFor, translateNode } from './narration.js';
import { createGeometry, codes, visibleNodes, greyCodes } from './geometry.js';

const node = (id, parent, status, label, extra = {}) => ({ node_id: id, parent_id: parent, status, label, description: 'A choice.',
  result: { metrics: { first_negative_month: 6 }, health: { score: 49.8 } }, ...extra });
const root = { current: '0', path: ['0'], nodes: [node('0', null, 'chosen', 'Today: student in Lausanne'),
  node('1', '0', 'child', 'Start working'), node('2', '0', 'child', "Do a master's"), node('3', '0', 'child', 'Move abroad')] };
const master = { current: '2', path: ['0', '2'], nodes: [node('0', null, 'chosen', 'Today: student in Lausanne'),
  node('2', '0', 'chosen', "Do a master's", { delta_vs_parent: { health_score: 29.8 } }),
  node('1', '0', 'sibling', 'Start working'), node('3', '0', 'sibling', 'Move abroad'),
  node('2.1', '2', 'child', 'Keep the student job only')] };

test('Lumi never re-reads a bubble: revisits only say "Back at"', () => {
  const n = createNarrator();
  const first = n.next(master, 'en');
  assert.equal(first.revisit, false);
  assert.match(first.speak, /^Do a master's\. .*month 7/);
  n.next(root, 'en');
  const again = n.next(master, 'en');
  assert.equal(again.revisit, true);
  assert.equal(again.text, first.text);
  assert.equal(again.speak, "Back at do a master's.");
  assert.equal(n.next(master, 'es').revisit, false, 'a new language is new content');
});

test('narration in another language never mixes in untranslated engine text', () => {
  assert.equal(translateNode({ label: 'Move abroad' }, 'de').label, 'Ins Ausland gehen');
  const custom = { ...root, nodes: [...root.nodes, node('4', '0', 'child', 'Open a bakery')] };
  const s = storyFor(custom, 'fr');
  assert.match(s, /partir à l'étranger/);
  assert.doesNotMatch(s, /bakery/);
});

test('greyed branches: siblings now, pruned ancestors-siblings later (client cache)', () => {
  const seen = new Map();
  visibleNodes(master, seen);
  const deep = { current: '2.1', path: ['0', '2', '2.1'], nodes: [node('0', null, 'chosen', 'T'), node('2', '0', 'chosen', 'M'),
    node('2.1', '2', 'chosen', 'K'), node('2.2', '2', 'sibling', 'L')] };
  const vis = visibleNodes(deep, seen);
  assert.deepEqual(vis.filter((n) => n.status === 'pruned').map((n) => n.node_id).sort(), ['1', '3']);
  assert.deepEqual([...greyCodes(vis)].sort(), [11, 12, 13, 22, 31, 32, 33]);
  assert.deepEqual(codes('2.3.1'), []);
});

test('nodes without their own still zoom into the deepest ancestor still (slots to level 4)', () => {
  const geo = createGeometry({ world: [1376, 768], hot: {}, nodes: { 2: 'c2', '2.1': 'c2_1', '2.1.3': null, '2.1.3.1': null },
    stills: { master: { rect: [0, 0, 1376, 768] }, c2: { rect: [408, 20, 560, 315] }, c2_1: { rect: [438, 80, 280, 157.5] } } });
  assert.equal(geo.stillFor('2.1.3.1'), 'c2_1');
  const r3 = geo.viewRect('2.1.3'), r4 = geo.viewRect('2.1.3.1');
  assert.ok(r3.w < 280 && r4.w < r3.w && r4.x >= r3.x && r4.x + r4.w <= r3.x + r3.w + 1e-9);
  assert.deepEqual(geo.viewRect('0'), { x: 0, y: 0, w: 1376, h: 768 });
});
