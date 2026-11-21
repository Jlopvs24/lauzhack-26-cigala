// Data for the path report (docs/report-spec.md §3), loaded in stages so the page never waits:
//  1. loadLevels: one /tree/expand per level of the path, in parallel (cached by the API, ~30-150 ms).
//     Enough for the hero, the stepper, every chart, the stress rows and the constraints.
//  2. loadExploration: /tree/explore per step, in parallel (~0.2-0.4 s): "what would have to be true"
//     and the tornado.
//  3. loadSummary: POST /report/summary in the background, only for the language model's wording of the
//     summary (seconds). The page shows a deterministic template until it arrives and never blocks on it.
import { apiRequest } from '../api.js';
import { personalFields } from '../personalize/store.js';
// Every request carries the user's own conditions (custom_nodes / node_patches) from the session store.

export function summary(r) {
  const m = r?.metrics || {}, goals = r?.goals || [];
  return {
    final_net_worth_real: m.final_net_worth_real ?? null, final_net_worth: r?.deterministic?.final_net_worth ?? m.final_net_worth ?? null,
    min_cash: m.min_cash ?? null, min_cash_month: m.min_cash_month ?? null, first_negative_month: m.first_negative_month ?? null, final_debt: m.final_debt ?? null,
    liquidity_months: m.liquidity_months ?? null, goals_met: goals.filter((g) => g.met_deterministic).length, goals_total: goals.length,
    plan_check: r?.plan_check?.level ?? null, plan_check_label: r?.plan_check?.label ?? null,
  };
}

const delta = (a, b, k) => (a?.metrics?.[k] != null && b?.metrics?.[k] != null ? Math.round((a.metrics[k] - b.metrics[k]) * 100) / 100 : null);
const series = (r) => ({ cash: r?.deterministic?.cash || [], net_worth: r?.deterministic?.net_worth || [], net_worth_real: r?.deterministic?.net_worth_real || [] });

export function expandBody({ profile, path, assumptions = [], uncertainty = false, weather = [] }) {
  return { path, assumptions, uncertainty, exploration: false, ...(weather?.length ? { weather } : {}), ...(profile ? { profile } : {}), ...personalFields() };
}

// Stage 1. `expand(path, isLeaf)` is injectable for tests; the lens (Monte Carlo) is asked for the leaf only.
export function loadLevels({ profile, path, assumptions = [], uncertainty = false, weather = [], expand, signal }) {
  const call = expand || ((p, leaf) => apiRequest('/tree/expand', { body: expandBody({ profile, path: p, assumptions, uncertainty: uncertainty && leaf, weather }), signal }));
  return Promise.all(Array.from({ length: path.length + 1 }, (_, i) => call(path.slice(0, i), i === path.length)));
}

export function buildFromLevels(levels, { profile, path, assumptions = [], uncertainty = false, startProfile = profile }) {
  const curOf = (d) => d.nodes.find((n) => n.node_id === d.current);
  const root = curOf(levels[0]);
  const steps = levels.slice(1).map((d, i) => {
    const n = curOf(d), parent = curOf(levels[i]);
    return {
      node_id: n.node_id, parent_id: n.parent_id, label: n.label, description: n.description, depth: n.depth, interventions: n.interventions || [], custom: !!(n.custom || n.origin === 'user'),
      changes: n.changes || [], assumptions_introduced: n.assumptions_introduced || [],
      delta_vs_parent: Object.fromEntries(['final_net_worth_real', 'final_net_worth', 'min_cash', 'final_debt', 'liquidity_months'].map((k) => [k, delta(n.result, parent.result, k)])),
      headline: n.result?.headline || null, result: n.result, summary: summary(n.result),
      alternatives: d.nodes.filter((x) => x.status === 'sibling' && x.result).map((x) => ({ node_id: x.node_id, label: x.label, description: x.description, status: 'sibling', summary: summary(x.result), headline: x.result.headline || null })),
    };
  });
  const last = levels.at(-1), leafNode = curOf(last);
  const leafRes = leafNode?.result;
  const cash = leafRes?.deterministic?.cash || [];
  const wr = leafRes?.weather_resilience;
  // the leaf and its siblings, with their monthly series, for the over-time chart
  const peers = last.nodes.filter((n) => n.result && (n.node_id === leafNode.node_id || (n.status === 'sibling' && n.parent_id === leafNode.parent_id)))
    .map((n) => ({ node_id: n.node_id, label: n.label, description: n.description, chosen: n.node_id === leafNode.node_id, ...series(n.result) }));
  const bands = leafRes?.bands;
  const lensOn = !!(uncertainty && leafRes?.n_paths && bands?.cash?.p10?.length);
  return {
    source: 'expand',
    engine_version: leafRes?.engine_version,
    question: { tree_id: last.tree_id, profile_id: last.profile_id, as_of: leafRes?.as_of, horizon_months: leafRes?.horizon_months, currency: leafRes?.currency || 'CHF',
      jurisdiction: 'Switzerland: official ESTV 2026 income tax by city and household (abroad: one assumed rate)', values: "nominal CHF; '_real' fields are in today's prices",
      path: ['0', ...path], question: [root, ...steps].map((s) => s.label).join(' -> ') },
    starting_state: Object.entries(startProfile?.provenance || {}).map(([field, p]) => ({ field, value: startProfile[field], label: p.source === 'questionnaire' ? 'user-entered' : p.source?.startsWith('ubs') ? 'synthetic' : p.source || 'synthetic', source: p.source, confidence: p.confidence })),
    baseline: { node_id: root.node_id, label: root.label, description: root.description, summary: summary(root.result), headline: root.result?.headline || null, result: root.result },
    steps,
    leaf: { node_id: leafNode.node_id, result: leafRes, tax_residence: leafRes?.tax_residence || [], constraints: leafRes?.constraints || [], plan_check: leafRes?.plan_check || null, weather_resilience: wr || null,
      goals: leafRes?.goals || [], monthly_surplus: cash.slice(1).map((v, i) => Math.round((v - cash[i]) * 100) / 100), peers,
      bands: lensOn ? { cash: bands.cash, net_worth: bands.net_worth } : null },
    stress: [{ weather: 'none', summary: summary(leafRes) }, ...(wr?.by_weather || []).filter((w) => w.holds !== null || w.status !== 'outside_horizon').map((w) => ({ weather: w.type, summary: {
      final_net_worth: w.final_net_worth, min_cash: w.min_cash, first_negative_month: w.first_negative_month, holds: w.holds, missed_goals: w.missed_goals } }))],
    uncertainty: lensOn ? { n_paths: leafRes.n_paths, seed: leafRes.seed,
      final_net_worth_p10: leafRes.metrics.final_net_worth_p10, final_net_worth_p50: leafRes.metrics.final_net_worth_p50, final_net_worth_p90: leafRes.metrics.final_net_worth_p90,
      shortfall_probability: leafRes.metrics.shortfall_probability } : null,
    validation: { checks: leafRes?.checks || [], seed: leafRes?.seed, engine_version: leafRes?.engine_version, trace_id: leafRes?.trace_id,
      reproduce: { route: 'POST /report', body: { path, assumptions, uncertainty, ...(profile ? { profile: '(the profile in "Starting point")' } : {}) } } },
    assumptions: last.assumptions || [],
    // macro perspective + qualitative factors (core #87): the request, the engine's applied events, the catalog
    outlook: { selected: Array.isArray(last.weather) ? last.weather : [], applied: leafRes?.weather_assumptions || leafRes?.weather || [], options: last.weather_options || {} },
  };
}

// Stage 2: exploration + tornado for every step, in parallel. Resolves to one entry per step (null on failure).
export function loadExploration({ profile, path, assumptions = [], weather = [], explore, signal }) {
  const call = explore || ((p) => apiRequest('/tree/explore', { body: { path: p, assumptions, ...(weather?.length ? { weather } : {}), ...(profile ? { profile } : {}), ...personalFields() }, signal }));
  return Promise.all(path.map((_, i) => call(path.slice(0, i + 1)).catch(() => null)));
}

export function mergeExploration(data, explored) {
  const steps = data.steps.map((st, i) => {
    const x = explored[i];
    if (!x) return st;
    return { ...st, result: { ...st.result, exploration: x.exploration ?? st.result?.exploration, sensitivity: x.sensitivity ?? st.result?.sensitivity }, facts: x.facts || [] };
  });
  return { ...data, steps, explored: true };
}

// Stage 3: the plain-language summary, worded by the language model. POST /report/summary (#43) rewords or
// translates the deterministic template and returns the template if any number is not in it; we only take
// its text. Older APIs without that route still word it inside POST /report. Never awaited by the first render.
const SUMMARY_KEY = 'cigala.summary.v1';
const summaryCache = new Map();
const readCache = () => { try { return JSON.parse(sessionStorage.getItem(SUMMARY_KEY) || '{}'); } catch { return {}; } };
function remember(key, value) {
  summaryCache.set(key, value);
  try { const all = readCache(); all[key] = value; const keys = Object.keys(all); if (keys.length > 40) delete all[keys[0]]; sessionStorage.setItem(SUMMARY_KEY, JSON.stringify(all)); } catch { /* blocked or full */ }
  return value;
}
export const clearSummaryCache = () => { summaryCache.clear(); try { sessionStorage.removeItem(SUMMARY_KEY); } catch { /* no storage */ } };

export async function loadSummary({ profile, path, assumptions = [], uncertainty = false, weather = [], lang = 'en', signal, request = apiRequest }) {
  const body = { path, assumptions, uncertainty, language: lang, ...(weather?.length ? { weather } : {}), ...(profile ? { profile } : {}), ...personalFields() };
  // the same report re-opened in this session never calls the language model again
  const key = JSON.stringify(body);
  const hit = summaryCache.get(key) ?? readCache()[key];
  if (hit) return hit;
  try {
    const s = await request('/report/summary', { body, signal });
    if (s?.text) return remember(key, { text: s.text, mode: s.mode || 'template', model: s.model, lang, testEvidence: [] });
  } catch (e) {
    if (!/ 40[45]\b/.test(e.message)) throw e; // only "route not there" falls back
  }
  const r = await request('/report', { body, signal });
  const s = r?.sections?.summary || r?.summary;
  if (!s?.text) return null;
  return remember(key, { text: s.text, mode: s.mode || 'template', model: s.model || r.model, lang, testEvidence: r?.sections?.validation?.test_evidence || [] });
}

export const loadLiveValidation = ({ signal } = {}) => apiRequest('/validation', { method: 'GET', signal });

// Stage 2b (core #48 item 6, thread 2's routes): what would fix the leaf, a 2-lever surface and a timing scan.
// Each one is optional: a failed or missing route gives null and its card is simply not drawn.
export const SURFACE_LEVERS = {
  x: { param: 'monthly_net_income', op: 'add', range: [0, 1500] },
  y: { param: 'monthly_rent', op: 'add', range: [-600, 0] },
};
export const fixTarget = (level) => ({ needs_financing: 'no_funding_gap', infeasible: 'feasible', holds_below_target: 'holds' })[level] || null;
export async function loadAnalyses({ profile, path, assumptions = [], weather = [], level, peer, request = apiRequest, signal }) {
  const base = { path, assumptions, ...(weather?.length ? { weather } : {}), ...(profile ? { profile } : {}), ...personalFields() };
  const target = fixTarget(level);
  const call = (route, extra) => request(route, { body: { ...base, ...extra }, signal }).catch(() => null);
  const [fix, surface, timing] = await Promise.all([
    target ? call('/tree/smallest_change', { target }) : null,
    path.length ? call('/tree/surface', { ...SURFACE_LEVERS, n: 5, ...(peer ? { compare_to: peer } : {}) }) : null,
    path.length ? call('/tree/timing_scan', {}) : null,
  ]);
  return { fix, surface, timing };
}
