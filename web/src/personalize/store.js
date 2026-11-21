// The user's own conditions for this session: patches on existing branches and custom branches.
// Persisted in sessionStorage; every expand / explore / report request spreads `requestFields()` into its
// body so the engine re-grows the tree with them. Changes are also broadcast as a window event
// `cigala:personal-change` {items, fields}, so any part of the app can refetch.
export const STORE_KEY = 'cigala.personal.v1';
export const CHANGE_EVENT = 'cigala:personal-change';

const memory = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) }; };
const defaultStorage = () => { try { if (typeof sessionStorage !== 'undefined') return sessionStorage; } catch { /* blocked */ } return memory(); };

export function createPersonalStore({ storage = defaultStorage(), key = STORE_KEY, target = typeof window !== 'undefined' ? window : null } = {}) {
  let items = [];
  try { items = JSON.parse(storage.getItem(key) || '[]'); if (!Array.isArray(items)) items = []; } catch { items = []; }
  const subs = new Set();
  const fields = () => requestFieldsOf(items);
  const save = () => {
    try { storage.setItem(key, JSON.stringify(items)); } catch { /* full or blocked: keep in memory */ }
    const snapshot = items.slice();
    subs.forEach((fn) => fn(snapshot));
    try { target?.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: { items: snapshot, fields: fields() } })); } catch { /* no DOM */ }
  };
  return {
    list: () => items.slice(),
    get: (id) => items.find((i) => i.id === id) || null,
    add(item) { items = [...items.filter((i) => i.id !== item.id), item]; save(); return item; },
    remove(id) { const before = items.length; items = items.filter((i) => i.id !== id); if (items.length !== before) save(); },
    clear() { if (items.length) { items = []; save(); } },
    subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },
    requestFields: fields,
    // the user's items that touch a node: patches on it, or the custom branch itself
    forNode: (nodeId) => items.filter((i) => (i.mode === 'patch' ? i.node_id === nodeId : i.custom_node?.node_id === nodeId)),
    isCustom: (nodeId) => items.some((i) => i.mode === 'branch' && i.custom_node?.node_id === nodeId),
  };
}

// {custom_nodes, node_patches}, only the keys that have something (older servers ignore nothing they get).
export function requestFieldsOf(items = []) {
  const out = {};
  const custom = items.filter((i) => i.mode === 'branch' && i.custom_node).map((i) => i.custom_node);
  const patches = {};
  for (const i of items) if (i.mode === 'patch' && i.node_patch) (patches[i.node_patch.node_id] ||= []).push(...(i.node_patch.interventions || []));
  if (custom.length) out.custom_nodes = custom;
  if (Object.keys(patches).length) out.node_patches = patches; // {node_id: [interventions...]}, appended in order
  return out;
}

// A path is valid while every custom node on it still exists: cut it at the first removed one.
export function validPath(path = [], store) {
  const i = path.findIndex((id) => /\.c\d+$/.test(id) && !store.isCustom(id));
  return i < 0 ? path : path.slice(0, i);
}

// The app-wide store (one per tab, survives reloads within the session).
export const personalStore = createPersonalStore();
export const personalFields = () => personalStore.requestFields();
