// Data for the full path report (docs/report-spec.md §3). Uses thread 2's POST /report when it exists;
// until then builds the same shape as core.report_data from /tree/expand calls along the path.
import { apiRequest } from '../api.js';

const LIMITATIONS = [
  'Synthetic profile and illustrative figures (UBS starter kit); assumptions with verified=false are modelling choices.',
  "Deterministic 'if these inputs hold, then...' paths under stated assumptions: not a forecast and not financial advice.",
  "One effective income-tax table (Lausanne, single person) at today's prices; no wealth tax, deductions or pillar 2/3a.",
  'One currency (CHF) with a constant exchange rate; non-financial assets (car, property) are not modelled.',
  'Shocks in the optional uncertainty lens are independent; its shares of paths are not real-world probabilities.',
  'Every number comes from the engine; the language model only words them and cannot compute new figures.',
];

export function summary(r) {
  const m = r?.metrics || {}, goals = r?.goals || [];
  return {
    final_net_worth_real: m.final_net_worth_real ?? null, final_net_worth: r?.deterministic?.final_net_worth ?? m.final_net_worth ?? null,
    min_cash: m.min_cash ?? null, first_negative_month: m.first_negative_month ?? null, final_debt: m.final_debt ?? null,
    liquidity_months: m.liquidity_months ?? null, goals_met: goals.filter((g) => g.met_deterministic).length, goals_total: goals.length,
    plan_check: r?.plan_check?.level ?? null, plan_check_label: r?.plan_check?.label ?? null,
  };
}

const delta = (a, b, k) => (a?.metrics?.[k] != null && b?.metrics?.[k] != null ? Math.round((a.metrics[k] - b.metrics[k]) * 100) / 100 : null);

export async function buildFromExpand({ profile, path, assumptions = [], uncertainty = false, expand }) {
  const call = expand || ((p) => apiRequest('/tree/expand', { body: { path: p, assumptions, uncertainty, ...(profile ? { profile } : {}) } }));
  const levels = [];
  for (let i = 0; i <= path.length; i++) levels.push(await call(path.slice(0, i)));
  const curOf = (d) => d.nodes.find((n) => n.node_id === d.current);
  const root = curOf(levels[0]);
  const steps = levels.slice(1).map((d, i) => {
    const n = curOf(d), parent = curOf(levels[i]);
    return {
      node_id: n.node_id, parent_id: n.parent_id, label: n.label, description: n.description, depth: n.depth, interventions: n.interventions || [],
      changes: n.changes || [], assumptions_introduced: n.assumptions_introduced || [],
      delta_vs_parent: Object.fromEntries(['final_net_worth_real', 'final_net_worth', 'min_cash', 'final_debt', 'liquidity_months'].map((k) => [k, delta(n.result, parent.result, k)])),
      headline: n.result?.headline || null, result: n.result,
      alternatives: d.nodes.filter((x) => x.status === 'sibling' && x.result).map((x) => ({ node_id: x.node_id, label: x.label, status: 'sibling', summary: summary(x.result), headline: x.result.headline || null })),
    };
  });
  const leafRes = steps.length ? steps.at(-1).result : root.result;
  const cash = leafRes?.deterministic?.cash || [];
  const wr = leafRes?.weather_resilience;
  const last = levels.at(-1);
  return {
    source: 'expand',
    engine_version: leafRes?.engine_version,
    question: { tree_id: last.tree_id, profile_id: last.profile_id, as_of: leafRes?.as_of, horizon_months: leafRes?.horizon_months, currency: leafRes?.currency || 'CHF',
      jurisdiction: 'Switzerland (Lausanne, Vaud): illustrative tax table', values: "nominal CHF; '_real' fields are in today's prices",
      path: ['0', ...path], question: [root, ...steps].map((s) => s.label).join(' -> ') },
    starting_state: Object.entries(profile?.provenance || {}).map(([field, p]) => ({ field, value: profile[field], label: p.source === 'questionnaire' ? 'user-entered' : p.source?.startsWith('ubs') ? 'synthetic' : p.source || 'synthetic', source: p.source, confidence: p.confidence })),
    baseline: { node_id: root.node_id, label: root.label, summary: summary(root.result), headline: root.result?.headline || null },
    steps,
    leaf: { node_id: steps.at(-1)?.node_id ?? '0', constraints: leafRes?.constraints || [], plan_check: leafRes?.plan_check || null, weather_resilience: wr || null,
      monthly_surplus: cash.slice(1).map((v, i) => Math.round((v - cash[i]) * 100) / 100) },
    stress: [{ weather: 'none', summary: summary(leafRes) }, ...(wr?.by_weather || []).map((w) => ({ weather: w.type, summary: {
      final_net_worth: w.final_net_worth, min_cash: w.min_cash, first_negative_month: w.first_negative_month, holds: w.holds, missed_goals: w.missed_goals } }))],
    uncertainty: uncertainty && leafRes?.n_paths ? { n_paths: leafRes.n_paths, seed: leafRes.seed, bands: leafRes.bands,
      final_net_worth_p10: leafRes.metrics.final_net_worth_p10, final_net_worth_p50: leafRes.metrics.final_net_worth_p50, final_net_worth_p90: leafRes.metrics.final_net_worth_p90,
      shortfall_probability: leafRes.metrics.shortfall_probability, note: 'Shares of simulated paths under these assumptions, not real-world probabilities.' } : null,
    validation: { checks: leafRes?.checks || [], seed: leafRes?.seed, engine_version: leafRes?.engine_version, trace_id: leafRes?.trace_id,
      reproduce: { route: 'POST /tree/expand', body: { path, assumptions, uncertainty, profile: profile ? '(the profile shown in section 3)' : 'demo (Alexia)' } } },
    limitations: LIMITATIONS,
    condition: 'Under these assumptions; not a forecast and not advice.',
  };
}

export async function fetchPathReport({ profile, path, assumptions = [], uncertainty = false }) {
  try {
    const data = await apiRequest('/report', { body: { path, assumptions, uncertainty, ...(profile ? { profile } : {}) } });
    if (data?.steps && data?.leaf) return { ...data, source: 'report' };
  } catch (e) {
    if (!/ 40[45]\b|returned 40[45]/.test(e.message)) throw e; // only "route not there yet" falls back
  }
  return buildFromExpand({ profile, path, assumptions, uncertainty });
}
