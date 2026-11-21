// Data layer of the comparison. ONE switch point: `loadComparison` asks `POST /tree/compare` (thread 2)
// and, when that route is not deployed (404/405/501) or returns a shape we cannot map, builds the same
// columns from the routes that exist: one /tree/expand per path (the node, its parent and the root
// "today" all carry results) plus /tree/explore, /tree/smallest_change and /tree/timing_scan for the
// "what would have to be true" rows. Every request carries profile, assumptions, weather and the
// user's personal conditions (custom_nodes / node_patches).
import { apiRequest } from '../api.js';
import { pathKey } from './model.js';

const clean = (p) => (p || []).map(String).filter((id) => id && id !== '0');
const missing = (e) => / (404|405|501)\b/.test(e?.message || '');

// A column from one /tree/expand response whose current node is the path's last node.
export function fromExpand(data, path) {
  const p = clean(path);
  const id = p.at(-1) || '0';
  const byId = new Map((data?.nodes || []).map((n) => [n.node_id, n]));
  const node = byId.get(id);
  if (!node?.result) return null;
  const parent = node.parent_id != null ? byId.get(node.parent_id) : null;
  const personal = [];
  for (const pid of p) {
    const n = byId.get(pid);
    if (n?.custom) personal.push({ node_id: pid, label: n.label, kind: 'custom' });
    else if (n?.patched) personal.push({ node_id: pid, label: (n.patch_interventions || []).map((i) => i.label).filter(Boolean).join(', ') || n.label, kind: 'patched' });
  }
  return {
    key: pathKey(p), path: p, node_id: id, label: node.label,
    crumbs: p.map((pid) => ({ id: pid, label: byId.get(pid)?.label || pid })),
    node, result: node.result,
    parent: parent?.result ? { node_id: parent.node_id, label: parent.label, result: parent.result } : null,
    baseline: byId.get('0')?.result || null,
    assumptions: data.assumptions || [], weather: data.weather || [], personal,
    exploration: node.result.exploration || null, smallest: null, timing: null,
  };
}

// /tree/compare (thread 2): accept `columns` or `paths` (or `results`) arrays of per-path objects that
// carry a SimulationResult. Returns null when the shape is not one we can read (→ fallback).
export function normalizeServer(r) {
  const list = Array.isArray(r?.columns) ? r.columns : Array.isArray(r?.paths) ? r.paths : Array.isArray(r?.results) ? r.results : null;
  if (!list?.length || !list.every((c) => c && (c.result || c.metrics))) return null;
  const baseline = r.baseline?.result || r.baseline || null;
  return list.map((c) => {
    const p = clean(c.path || []);
    const result = c.result || c;
    const parent = c.parent?.result ? c.parent : c.impact_alone?.parent ? { node_id: c.impact_alone.parent.node_id, label: c.impact_alone.parent.label, result: c.impact_alone.parent.result || c.impact_alone.parent } : null;
    return {
      key: pathKey(p), path: p, node_id: c.node_id || p.at(-1) || '0', label: c.label || p.at(-1) || '',
      crumbs: c.crumbs || (c.labels ? p.map((id, i) => ({ id, label: c.labels[i] || id })) : p.map((id) => ({ id, label: id }))),
      node: c.node || null, result,
      parent: parent?.result?.metrics ? parent : null,
      baseline: c.baseline?.metrics ? c.baseline : baseline?.metrics ? baseline : null,
      impact_alone: c.impact_alone || null,
      assumptions: r.assumptions || c.assumptions || [], weather: r.weather || [], personal: c.personal || [],
      exploration: c.exploration || result.exploration || null, smallest: c.smallest_change || null, timing: c.timing_scan || null,
    };
  });
}

/**
 * Load the columns for `paths`. `fields` = {custom_nodes?, node_patches?}. `onPartial(cols)` fires
 * once the outcome rows are ready (the what-if rows arrive a moment later).
 */
export async function loadComparison({ paths, profile, assumptions = [], weather = [], fields = {}, request = apiRequest, signal, onPartial } = {}) {
  const ps = paths.map(clean);
  const common = { assumptions, weather, ...fields, ...(profile ? { profile } : {}) };
  try {
    const cols = normalizeServer(await request('/tree/compare', { body: { paths: ps, baseline: [], ...common }, signal }));
    if (cols) return cols;
  } catch (e) {
    if (signal?.aborted || !missing(e)) throw e;
  }
  // fallback: one expand per path (fast path, no exploration), then the what-ifs in parallel
  const cols = (await Promise.all(ps.map((p) => request('/tree/expand', { body: { path: p, exploration: false, uncertainty: false, ...common }, signal }).then((d) => fromExpand(d, p)))))
    .filter(Boolean);
  onPartial?.(cols);
  const soft = (route, body) => request(route, { body: { ...body, ...common }, signal }).catch((e) => { if (signal?.aborted) throw e; return null; });
  await Promise.all(cols.map(async (c) => {
    if (!c.path.length) return;
    const [x, s, t] = await Promise.all([
      c.exploration ? null : soft('/tree/explore', { path: c.path }),
      soft('/tree/smallest_change', { path: c.path }),
      soft('/tree/timing_scan', { path: c.path }),
    ]);
    if (x?.exploration) c.exploration = x.exploration;
    c.smallest = s; c.timing = t;
  }));
  return cols.map((c) => ({ ...c }));
}
