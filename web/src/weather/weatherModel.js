// Weather on the tree (#65): what the user does not choose, applied to every visible node.
// Pure helpers (tested with node --test). The engine computes every number; this file only
// builds the request, counts which options still hold (from each node's plan_check) and words
// it conditionally ("if a recession starts in month 12…"), never as a forecast.
import { W_I18N, M_I18N } from './weatherI18n.js';

export const KNOWN = ['recession', 'inflation', 'market_crash', 'job_loss', 'chf_strengthens', 'chf_weakens'];
// weathers that take a duration (months); the others are one-off (crash) or last to the horizon (FX)
export const WITH_DURATION = new Set(['recession', 'inflation', 'job_loss']);
export const START_MAX = 60;
export const DURATION_MAX = 36;
// how heavy each weather looks on the scene (thread 6's visual layer), 0..1 after summing
const WEIGHT = { recession: 1, market_crash: 0.8, job_loss: 0.7, inflation: 0.5, chf_strengthens: 0.3, chf_weakens: 0.2 };
const EXCLUSIVE = { chf_strengthens: 'chf_weakens', chf_weakens: 'chf_strengthens' };

export const CLEAR = Object.freeze({ types: [], start: 12, duration: null });

const wl = (lang) => W_I18N[lang] || W_I18N.en;

/** Chips from the engine's catalog (`tree.weather_options`: {type: description}); known order first. */
export function weatherOptions(tree, lang = 'en') {
  const opts = tree?.weather_options || {};
  const types = [...KNOWN.filter((k) => k in opts), ...Object.keys(opts).filter((k) => !KNOWN.includes(k) && !k.includes(':'))];
  const L = wl(lang);
  return types.map((type) => ({ type, label: L.names[type] || type.replace(/_/g, ' '), description: L.descriptions[type] || opts[type] || '' }));
}

/** Toggle one weather; the two FX directions exclude each other. */
export function toggle(sel, type) {
  const on = sel.types.includes(type);
  const types = on ? sel.types.filter((t) => t !== type) : [...sel.types.filter((t) => t !== EXCLUSIVE[type]), type];
  return { ...sel, types };
}

const clampInt = (v, lo, hi) => Math.min(hi, Math.max(lo, Math.round(Number(v) || 0)));

/** The `weather` list for /tree/expand: one event per selected type, sharing the start month. */
export function buildWeather(sel) {
  const start = clampInt(sel.start, 0, START_MAX);
  return sel.types.map((type) => {
    const ev = { type, start_month: start };
    if (sel.duration != null && WITH_DURATION.has(type)) ev.duration_months = clampInt(sel.duration, 1, DURATION_MAX);
    return ev;
  });
}

export function intensity(weather) {
  return Math.min(1, Math.round((weather || []).reduce((s, w) => s + (WEIGHT[w.type] ?? 0.5), 0) * 100) / 100);
}

/** The options the user is choosing between now: the current node's children, else it and its siblings. */
export function optionNodes(tree) {
  const nodes = tree?.nodes || [];
  const kids = nodes.filter((n) => n.status === 'child');
  if (kids.length) return kids;
  return nodes.filter((n) => n.node_id === tree?.current || n.status === 'sibling');
}

const holds = (n) => n?.result?.plan_check?.feasible === true;

/** How many of the options still hold under the weather (from the engine's plan_check). */
export function stormSummary(tree) {
  const opts = optionNodes(tree).filter((n) => n.result?.plan_check);
  const holding = opts.filter(holds).map((n) => n.node_id);
  const breaking = opts.filter((n) => !holds(n)).map((n) => n.node_id);
  return { held: holding.length, of: opts.length, holding, breaking };
}

function joinList(items, and) {
  if (items.length <= 1) return items.join('');
  return `${items.slice(0, -1).join(', ')} ${and} ${items.at(-1)}`;
}

/** "If a recession starts in month 12: 2 of 3 options still hold." Null under a clear sky. */
export function stormLine(lang, weather, summary) {
  if (!weather?.length) return null;
  const L = wl(lang);
  if (weather.some((w) => w.level)) {
    const labels = weather.map((w) => M_I18N[lang]?.labels[`${w.type}:${w.level}`] || M_I18N.en.labels[`${w.type}:${w.level}`] || L.names[w.type] || w.type);
    const condition = (M_I18N[lang] || M_I18N.en).condition(joinList(labels, L.and));
    return !summary?.of ? condition : `${condition}${L.sep}${L.holdCount(summary.held, summary.of)}`;
  }
  const what = joinList(weather.map((w) => L.phrase[w.type] || w.type), L.and);
  const month = (weather[0].start_month ?? 0) + 1;
  const cond = L.ifStarts(what, month, weather.length > 1);
  if (!summary || !summary.of) return `${cond}.`;
  return `${cond}${L.sep}${L.holdCount(summary.held, summary.of)}`;
}

/** Detail of the window event 'weather:change' (contract posted on the board for thread 6). */
export function eventDetail(weather, tree, pending) {
  const s = pending || !tree ? null : stormSummary(tree);
  return {
    weather: visualWeather(weather), selected_weather: weather, intensity: intensity(visualWeather(weather)), clear: !weather.length, pending: !!pending,
    start_month: weather[0]?.start_month ?? null,
    holds: s ? { held: s.held, of: s.of } : null,
    holding_node_ids: s ? s.holding : [], breaking_node_ids: s ? s.breaking : [],
  };
}

export function sameWeather(a, b) {
  return JSON.stringify(a || []) === JSON.stringify(b || []);
}

// Qualitative requests contain no numeric controls; only the engine assigns magnitudes.
export const MACRO_CLEAR = Object.freeze({ scenario: 'neutral', factors: {} });
export const FACTORS = ['inflation', 'fx', 'markets', 'jobs', 'rates'];
export const SCENARIOS = ['pessimistic', 'neutral', 'optimistic'];
export function selectScenario(level) {
  return { scenario: level, factors: {} };
}
export function toggleFactor(sel, type, level) {
  const factors = { ...sel.factors };
  if (factors[type] === level) delete factors[type];
  else factors[type] = level;
  return { ...sel, factors };
}
export function buildMacroWeather(sel) {
  return [...(sel.scenario === 'neutral' ? [] : [{ type: 'scenario', level: sel.scenario }]),
    ...FACTORS.filter((type) => sel.factors[type]).map((type) => ({ type, level: sel.factors[type] }))];
}
export function macroOptions(tree, type) {
  return Object.values(tree?.weather_options || {}).filter((o) => o && typeof o === 'object' && o.type === type && o.level);
}
export function visualWeather(weather) {
  const aliases = { 'scenario:pessimistic': ['recession', 'inflation'], 'scenario:neutral': [], 'scenario:optimistic': [],
    'inflation:high': ['inflation'], 'inflation:low': [], 'fx:chf_strong': ['chf_strengthens'], 'fx:chf_weak': ['chf_weakens'],
    'markets:crash': ['market_crash'], 'markets:boom': [], 'jobs:weak': ['recession'], 'jobs:strong': [], 'rates:up': [], 'rates:down': [] };
  const out = [];
  for (const w of weather || []) {
    const types = w.level ? aliases[`${w.type}:${w.level}`] || [] : [w.type];
    for (const type of types) if (!(type === 'inflation' && w.type === 'scenario' && weather.some((e) => e.type === 'inflation' && e.level === 'low')) && !out.some((e) => e.type === type)) out.push({ ...w, type });
  }
  return out;
}
