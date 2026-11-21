// The comparison selection for this session: up to 4 paths from any branch, persisted in sessionStorage.
// Changes are broadcast as `cigala:compare-change` {items}; `openCompare({paths})` asks the mounted
// <CompareRoot/> to open the comparison page (`cigala:compare-open`). The latest weather from
// web/src/weather (`weather:change`) is remembered so the comparison uses the same sky as the tree.
import { MAX_COMPARE, pathKey } from './model.js';

export const COMPARE_KEY = 'cigala.compare.v1';
export const COMPARE_CHANGE = 'cigala:compare-change';
export const COMPARE_OPEN = 'cigala:compare-open';

const memory = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)) }; };
const defaultStorage = () => { try { if (typeof sessionStorage !== 'undefined') return sessionStorage; } catch { /* blocked */ } return memory(); };
const clean = (p) => (Array.isArray(p) ? p.map(String).filter((id) => id && id !== '0') : []);

export function createCompareStore({ storage = defaultStorage(), key = COMPARE_KEY, target = typeof window !== 'undefined' ? window : null, max = MAX_COMPARE } = {}) {
  let items = [];
  try { items = JSON.parse(storage.getItem(key) || '[]'); if (!Array.isArray(items)) items = []; } catch { items = []; }
  items = items.filter((i) => i && Array.isArray(i.path)).slice(0, max);
  const subs = new Set();
  let snap = Object.freeze(items.slice()); // stable between changes (React's useSyncExternalStore)
  const save = () => {
    try { storage.setItem(key, JSON.stringify(items)); } catch { /* full or blocked: memory only */ }
    snap = Object.freeze(items.slice());
    subs.forEach((fn) => fn(snap));
    try { target?.dispatchEvent(new CustomEvent(COMPARE_CHANGE, { detail: { items: snap } })); } catch { /* no DOM */ }
  };
  const api = {
    max,
    list: () => snap,
    has: (path) => items.some((i) => i.key === pathKey(clean(path))),
    full: () => items.length >= max,
    /** {path, label, crumbs?} → false when full or already there */
    add({ path, label = '', crumbs = [] }) {
      const p = clean(path), k = pathKey(p);
      if (items.some((i) => i.key === k) || items.length >= max) return false;
      items = [...items, { key: k, path: p, label: label || p.at(-1) || '0', crumbs }];
      save();
      return true;
    },
    remove(pathOrKey) {
      const k = typeof pathOrKey === 'string' ? pathOrKey : pathKey(clean(pathOrKey));
      const before = items.length;
      items = items.filter((i) => i.key !== k);
      if (items.length !== before) save();
    },
    toggle(item) { if (api.has(item.path)) { api.remove(item.path); return false; } return api.add(item); },
    clear() { if (items.length) { items = []; save(); } },
    subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },
    // drop paths whose custom node no longer exists (personal conditions removed)
    prune(isValid) { const next = items.filter((i) => isValid(i.path)); if (next.length !== items.length) { items = next; save(); } },
  };
  return api;
}

export const compareStore = createCompareStore();

/** Open the comparison page. `paths` = explicit paths (e.g. the options here); none = the pinned selection. */
export function openCompare({ paths, labels, source } = {}) {
  try { window.dispatchEvent(new CustomEvent(COMPARE_OPEN, { detail: { paths: paths?.map(clean), labels, source: source || (paths ? 'options' : 'pinned') } })); } catch { /* no DOM */ }
}

// latest weather on the tree (Lluc's control fires `weather:change` {weather, pending})
let lastWeather = [];
export const currentWeather = () => lastWeather;
if (typeof window !== 'undefined') {
  window.addEventListener('weather:change', (e) => { if (Array.isArray(e.detail?.weather)) lastWeather = e.detail.weather; });
}
