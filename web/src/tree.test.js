import test from 'node:test';
import assert from 'node:assert/strict';
import { pathToNode, validateTree } from './tree.js';

const makeNode = (node_id, parent_id, status) => ({ node_id, parent_id, status,
  label: node_id, result: { metrics: { final_net_worth_p50: 8000, min_cash: -500 } } });
const nodes = [makeNode('root', null, 'chosen'), makeNode('study', 'root', 'chosen'),
  makeNode('work', 'root', 'sibling'), makeNode('scholarship', 'study', 'child')];

test('navigate two levels, switch siblings, and go back without keeping the old branch', () => {
  assert.deepEqual(pathToNode(nodes, 'scholarship'), ['study', 'scholarship']);
  assert.deepEqual(pathToNode(nodes, 'work'), ['work']);
  assert.deepEqual(pathToNode(nodes, 'study'), ['study']);
  assert.deepEqual(pathToNode(nodes, 'root'), []);
});
test('reject stale branches, missing parents and cycles', () => {
  assert.throws(() => pathToNode(nodes, 'missing'));
  assert.throws(() => pathToNode([makeNode('orphan', 'missing', 'child')], 'orphan'));
  assert.throws(() => pathToNode([makeNode('a', 'b', 'chosen'), makeNode('b', 'a', 'child')], 'a'));
});
test('accept valid negative cash; reject incomplete, duplicate, or invalid API results', () => {
  const data = { nodes, current: 'study', path: ['root', 'study'] };
  assert.equal(validateTree(data), data);
  assert.throws(() => validateTree({}));
  assert.throws(() => validateTree({ ...data, nodes: [...nodes, nodes[0]] }));
  assert.throws(() => validateTree({ ...data, nodes: [makeNode('study', null, 'pruned')] }));
  assert.throws(() => validateTree({ ...data, nodes: [{ ...nodes[1], result: {} }] }));
});
