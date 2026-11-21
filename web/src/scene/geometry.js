// Pure geometry of the photographic tree. The world is the master photo's frame (1376 x 768 units).
// public/tree/stills.json gives each still's rectangle in that world and a slot per decision node
// down to level 4 (null = no still rendered yet: the camera zooms into the deepest ancestor still).

export const CROWN = { 1: [420, 215], 2: [675, 92], 3: [965, 228] }; // limb label anchors
const DEEP = [[0.27, 0.42], [0.5, 0.28], [0.73, 0.44]]; // child framing inside a still-less parent

export const parts = (id) => String(id).split('.').map(Number);
export const parentId = (id) => (parts(id).length === 1 ? '0' : parts(id).slice(0, -1).join('.'));

export function createGeometry(meta) {
  const [W, H] = meta.world || [1376, 768];
  const rectOf = (name) => { const [x, y, w, h] = meta.stills[name].rect; return { x, y, w, h }; };
  const ownStill = (id) => (!id || id === '0' ? 'master' : meta.nodes?.[id] || null);
  const hasStill = (name) => !!(name && meta.stills[name]);
  function stillFor(id) {
    for (let x = id || '0'; ; x = parentId(x)) {
      if (hasStill(ownStill(x))) return ownStill(x);
      if (x === '0') return 'master';
    }
  }
  function viewRect(id) {
    if (!id || id === '0') return { x: 0, y: 0, w: W, h: H };
    if (hasStill(ownStill(id))) return rectOf(ownStill(id));
    const f = meta.frames?.[id]; // a still-less node framed on foliage inside its parent's still (precomputed)
    if (f) return { x: f[0], y: f[1], w: f[2], h: f[3] };
    const base = viewRect(parentId(id));
    const [fx, fy] = DEEP[(parts(id).at(-1) - 1) % 3] || [0.5, 0.5];
    const w = base.w * 0.58, h = base.h * 0.58;
    const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
    return { x: clamp(base.x + base.w * fx - w / 2, base.x, base.x + base.w - w),
      y: clamp(base.y + base.h * fy - h / 2, base.y, base.y + base.h - h), w, h };
  }
  function anchor(id) {
    if (id === '0') return [W / 2, 560];
    const p = parts(id);
    if (p.length === 1 && CROWN[p[0]]) return CROWN[p[0]];
    if (p.length === 2 && meta.hot?.[p[0]]?.[p[1] - 1]) return meta.hot[p[0]][p[1] - 1];
    const r = viewRect(parentId(id));
    const [fx, fy] = DEEP[(p.at(-1) - 1) % 3] || [0.5, 0.5];
    return [r.x + r.w * fx, r.y + r.h * fy];
  }
  return { W, H, rectOf, ownStill, hasStill, stillFor, viewRect, anchor };
}

// Label-map codes a node greys out: a limb covers its three sub-branches; deeper nodes have no mask yet.
export function codes(id) {
  const p = parts(id);
  if (p.some((n) => !(n >= 1 && n <= 3))) return [];
  if (p.length === 1) return [p[0] * 10 + 1, p[0] * 10 + 2, p[0] * 10 + 3];
  if (p.length === 2) return [p[0] * 10 + p[1]];
  return [];
}

// Visible nodes = API nodes + branches pruned earlier (siblings of every ancestor), kept from a
// client cache when the API does not return them as status "pruned".
export function visibleNodes(data, seen) {
  const nodes = data.nodes.map((n) => ({ ...n }));
  for (const n of nodes) seen.set(n.node_id, { label: n.label, parent_id: n.parent_id });
  const ids = new Set(nodes.map((n) => n.node_id));
  const chain = data.path || ['0'];
  const ancestors = new Set(chain.slice(0, -1));
  for (const [id, s] of seen) {
    if (!ids.has(id) && ancestors.has(s.parent_id) && !chain.includes(id)) {
      nodes.push({ node_id: id, parent_id: s.parent_id, label: s.label, status: 'pruned' });
    }
  }
  return nodes;
}

export const greyCodes = (nodes) => new Set(nodes.filter((n) => n.status === 'sibling' || n.status === 'pruned').flatMap((n) => codes(n.node_id)));
