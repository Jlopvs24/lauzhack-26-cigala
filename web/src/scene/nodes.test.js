import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { NODES } from './i18n.js';
import { translateNode } from './narration.js';

const tree = JSON.parse(readFileSync(new URL('../../../core/data/trees/alexia.json', import.meta.url), 'utf8'));
const all = (n) => [n, ...(n.children || []).flatMap(all)];

test('every node of the engine tree has ES/FR/DE texts that match its current English text', () => {
  const missing = [];
  for (const n of all(tree.root)) {
    const row = NODES[n.label];
    if (!row) { missing.push(`missing ${n.node_id} ${n.label}`); continue; }
    if (row.en[0] !== n.label || row.en[1] !== (n.description || '')) missing.push(`stale ${n.node_id} ${n.label}`);
    for (const l of ['es', 'fr', 'de']) if (!row[l]?.[0] || !row[l]?.[1]) missing.push(`${l} ${n.node_id} ${n.label}`);
  }
  assert.deepEqual(missing, [], 'run: python web/scripts/node-texts.py --write, then translate the new rows');
});

test('a changed engine description is never read with an old translation', () => {
  const t = translateNode({ label: 'Share a flat', description: 'A shared flat: CHF 700 a month less rent.' }, 'es');
  assert.equal(t.label, 'Compartir piso');
  assert.equal(t.descKnown, false);
  assert.equal(translateNode({ label: 'Open a bakery' }, 'fr').known, false);
});
