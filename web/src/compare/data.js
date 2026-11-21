// Data layer of the comparison. ONE switch point: `loadComparison` asks `POST /tree/compare` (thread 2)
// and, when that route is not deployed (404/405/501) or returns a shape we cannot map, builds the same
// columns from the routes that exist: one /tree/expand per path (the node, its parent and the root
// "today" all carry results) plus /tree/explore, /tree/smallest_change and /tree/timing_scan for the
// "what would have to be true" rows. Every request carries profile, assumptions, weather and the
// user's personal conditions (custom_nodes / node_patches).
import { apiRequest } from '../api.js';
import { pathKey } from './model.js';

const clean = (p) => (p || []).map(String).filter((id) => id && id !== '0');

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

// /tree/compare (thread 2, docs/contracts.md "Compare options"): `options[]` with metrics, plan_check,
// series and impact_alone {vs_parent, vs_today: {node_id, label, delta}}. Returns null when the shape
// is not one we can read (→ fallback).
export function normalizeServer(r) {
  const list = Array.isArray(r?.options) ? r.options : null;
  if (!list?.length || !list.every((o) => o && o.metrics)) return null;
  return list.map((o) => {
    const p = clean(o.path || []);
    const labels = o.path_labels || [];
    const pl = labels.length === p.length ? labels : p.map((id, i) => labels[i - (p.length - labels.length)] || id);
    const m = o.metrics;
    const result = {
      metrics: m, plan_check: o.plan_check || null, headline: o.headline || null,
      deterministic: { net_worth: o.series?.net_worth || [], net_worth_real: o.series?.net_worth_real || [], cash: o.series?.cash || [] },
      weather_resilience: o.weather_resilience || null, assumptions_used: o.assumptions_used || null, trace_id: o.trace_id,
    };
    const personal = [];
    if (o.custom) personal.push({ node_id: o.node_id, label: o.label, kind: 'custom' });
    else if (o.patched) personal.push({ node_id: o.node_id, label: o.label, kind: 'patched' });
    return {
      key: pathKey(p), path: p, node_id: o.node_id || p.at(-1) || '0', label: o.label || p.at(-1) || '',
      crumbs: p.map((id, i) => ({ id, label: pl[i] || id })), node: null, result,
      parent: null, baseline: null, impact: o.impact_alone || null,
      assumptions: r.assumptions || [], weather: r.weather || [], personal,
      exploration: null, smallest: null, timing: null,
    };
  });
}

// One pinned path: compare it with its siblings (same parent), up to 4 columns in all.
export async function withAlternatives(path, { request = apiRequest, signal, body = {} } = {}) {
  try {
    const d = await request('/tree/expand', { body: { path, exploration: false, uncertainty: false, ...body }, signal });
    const sibs = (d?.nodes || []).filter((n) => n.status === 'sibling').map((n) => [...path.slice(0, -1), n.node_id]);
    return [path, ...sibs].slice(0, 4);
  } catch (e) {
    if (signal?.aborted) throw e;
    return [path];
  }
}

/**
 * Load the columns for `paths`. `fields` = {custom_nodes?, node_patches?}. `onPartial(cols)` fires
 * once the outcome rows are ready (the what-if rows arrive a moment later).
 */
export async function loadComparison({ paths, profile, assumptions = [], weather = [], fields = {}, request = apiRequest, signal, onPartial } = {}) {
  let ps = paths.map(clean);
  if (ps.length === 1 && ps[0].length) ps = await withAlternatives(ps[0], { request, signal, body: { assumptions, weather, ...fields, ...(profile ? { profile } : {}) } });
  const common = { assumptions, weather, ...fields, ...(profile ? { profile } : {}) };
  let cols = null;
  if (ps.length >= 2 && ps.length <= 4) {
    try {
      cols = normalizeServer(await request('/tree/compare', { body: { paths: ps, baseline: 'parent', ...common }, signal }));
    } catch (e) {
      if (signal?.aborted || !/ (404|405|422|501)\b/.test(e?.message || '')) throw e;
    }
  }
  // fallback: one expand per path (fast path, no exploration)
  if (!cols) {
    cols = (await Promise.all(ps.map((p) => request('/tree/expand', { body: { path: p, exploration: false, uncertainty: false, ...common }, signal }).then((d) => fromExpand(d, p)))))
      .filter(Boolean);
  }
  onPartial?.(cols);
  // then the what-ifs, in parallel, whatever answered first
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
