// Pure derivations for the visual path report: formatting, the hero numbers, the "if… then…" line,
// the "what would have to be true" cards, the tornado, stress and constraint rows. No network, no DOM,
// so it runs under `node --test`. Every number here is read from engine fields; nothing is estimated.
import { ri } from './reportI18n.js';
import { H_I18N } from '../scene/headline.js';

const MINUS = '−';
export const chf = (n) => (Number.isFinite(n) ? (n < 0 ? MINUS : '') + 'CHF ' + Math.abs(Math.round(n)).toLocaleString('en-US').replace(/,/g, '’') : '–');
export const signedChf = (n) => (Number.isFinite(n) ? (n > 0.5 ? '+' : n < -0.5 ? MINUS : '±') + chf(Math.abs(n)) : '–');
export const dec = (n, d = 1) => (Number.isFinite(n) ? String(Math.round(n * 10 ** d) / 10 ** d).replace('-', MINUS) : '–');
export const month1 = (i) => (Number.isFinite(i) ? i + 1 : null); // engine months are 0-based
// compact numbers for axes and tight labels: 120k, −3.8k, 1.2M
export function compact(n) {
  if (!Number.isFinite(n)) return '–';
  const a = Math.abs(n), s = n < 0 ? MINUS : '';
  if (a >= 1e6) return s + dec(a / 1e6, a >= 1e7 ? 0 : 1) + 'M';
  if (a >= 1e3) return s + dec(a / 1e3, a >= 1e4 ? 0 : 1) + 'k';
  return s + Math.round(a);
}
const num = (n) => (Number.isFinite(n) ? (Math.abs(n) >= 1000 ? Math.round(n).toLocaleString('en-US').replace(/,/g, '’') : String(Math.round(n * 100) / 100)) : '–');
// unit-aware assumption value: rates per year as %, multipliers as ×, CHF amounts with their period
export function fmtVal(v, unit = '') {
  if (!Number.isFinite(v)) return '–';
  if (/^1\/year$|^share/.test(unit)) return `${Math.round(v * 1000) / 10}%`;
  if (unit === 'multiplier') return `×${Math.round(v * 100) / 100}`;
  if (/^CHF/.test(unit)) return `${chf(v)}${unit.slice(3)}`;
  return `${num(v)}${unit ? ' ' + unit : ''}`;
}

const leafOf = (data) => data.steps.at(-1) || data.baseline;
export const leafSummary = (data) => leafOf(data)?.summary || {};

export function pathPhrase(data, lang, tr) {
  const L = ri(lang);
  return data.steps.map((s) => L.q(tr(s).label)).join(L.then);
}

// Hero sentence, deterministic, in the UI language.
export function oneLiner(data, lang, tr) {
  const L = ri(lang), s = leafSummary(data);
  if (!data.steps.length) return L.lineNone(chf(s.final_net_worth_real));
  if (s.first_negative_month != null) return L.lineGap(s.first_negative_month + 1, chf(s.final_net_worth_real));
  return L.lineHolds(chf(s.final_net_worth_real));
}

export const levelTone = (level) => (level === 'holds' ? 'good' : level === 'holds_below_target' ? 'warn' : 'bad');

// The 4 key numbers: plan check, funding gap (or tightest buffer), real net worth, goals.
export function heroTiles(data, lang) {
  const L = ri(lang), H = H_I18N[lang] || H_I18N.en, s = leafSummary(data), leaf = data.leaf || {};
  const level = leaf.plan_check?.level || s.plan_check || (s.first_negative_month != null ? 'needs_financing' : 'holds');
  const wr = leaf.weather_resilience;
  const tiles = [{ key: 'plan', label: L.tPlan, value: H.level[level] || level, sub: wr?.of ? H.holdsWeather(wr.holds_in ?? 0, wr.of) : '', tone: levelTone(level) }];
  if (s.first_negative_month != null) {
    const gap = (leaf.constraints || []).find((c) => c.name === 'no_funding_gap');
    tiles.push({ key: 'gap', label: L.tGap, value: chf(Math.abs(s.min_cash)), sub: L.gapSub(s.first_negative_month + 1, gap?.months_in_breach), tone: 'bad' });
  } else {
    tiles.push({ key: 'buffer', label: L.tBuffer, value: L.months(dec(s.liquidity_months)), sub: L.bufSub((s.min_cash_month ?? 0) + 1), tone: s.liquidity_months < 3 ? 'warn' : 'good' });
  }
  tiles.push({ key: 'nw', label: L.tNw, value: chf(s.final_net_worth_real), sub: L.nwSub(chf(s.final_net_worth)), tone: 'neutral' });
  const missed = (leaf.goals || []).filter((g) => !g.met_deterministic).map((g) => g.name);
  tiles.push({ key: 'goals', label: L.tGoals, value: L.goalsOf(s.goals_met ?? 0, s.goals_total ?? 0), sub: missed.length ? L.missing(missed.join(', ')) : s.goals_total ? L.allGoals : '', tone: missed.length ? 'warn' : 'good' });
  return tiles;
}

// Template for "In plain words" until (or instead of) the language model's wording.
export function plainTemplate(data, lang, tr) {
  const L = ri(lang), wr = data.leaf?.weather_resilience;
  const cards = data.steps.length ? whatIfCards(data.steps.at(-1), lang, tr) : [];
  const be = cards.find((c) => c.key === 'break');
  const fact = be ? `${be.big}: ${be.text}` : '';
  return L.plain(wr?.holds_in ?? 0, wr?.of ?? 0, fact);
}

// "What would have to be true" for one step: up to 4 cards {key, title, big, text, tone, more[]}.
export function whatIfCards(step, lang, tr) {
  const L = ri(lang), ex = step?.result?.exploration, m = step?.result?.metrics || {};
  if (!ex) return [];
  const cards = [];
  const peer = (label) => L.q(tr({ label }).label);
  const rs = ex.reverse_stress;
  if (rs) {
    if (rs.status === 'already_broken') cards.push({ key: 'shock', title: L.cShock, big: L.cShockNone, text: L.cShockBroken(month1(rs.result?.first_negative_month ?? m.first_negative_month)), tone: 'bad' });
    else if (rs.status === 'threshold_found' && Number.isFinite(rs.value)) cards.push({ key: 'shock', title: L.cShock, big: chf(rs.value), text: L.cShockOk, tone: 'good' });
    else if (rs.status === 'not_reached_within_bounds') cards.push({ key: 'shock', title: L.cShock, big: chf(rs.bounds?.[1]) + '+', text: L.cShockMax(chf(rs.bounds?.[1])), tone: 'good' });
  }
  const be = (ex.break_even || []).filter((b) => Number.isFinite(b.delta_final_net_worth));
  if (be.length) {
    const lever = (id) => (ex.levers || []).find((l) => l.assumption_id === id)?.label || id;
    const line = (b) => `${signedChf(b.delta_final_net_worth)} ${b.delta_final_net_worth >= 0 ? L.cAhead(peer(b.label)) : L.cBehind(peer(b.label))}`;
    const th = be.find((b) => b.salary_threshold?.status === 'threshold_found' && Number.isFinite(b.salary_threshold.value));
    if (th) {
      const t = th.salary_threshold;
      cards.push({ key: 'break', title: L.cBreak, big: fmtVal(t.value, t.unit), text: L.cLevel(lever(t.assumption_id), peer(th.label)), tone: 'neutral', more: be.map(line) });
    } else {
      const b = [...be].sort((x, y) => Math.abs(y.delta_final_net_worth) - Math.abs(x.delta_final_net_worth))[0];
      const d = b.delta_final_net_worth;
      let text = d >= 0 ? L.cAhead(peer(b.label)) : L.cBehind(peer(b.label));
      if (Number.isFinite(b.sustained_crossover_month) && b.sustained_crossover_month > 0) text += L.cFromM(b.sustained_crossover_month + 1);
      else if (d < 0) text += L.cNever;
      cards.push({ key: 'break', title: L.cBreak, big: signedChf(d), text, tone: d >= 0 ? 'good' : 'bad', more: be.filter((x) => x !== b).map(line) });
    }
  }
  const gs = ex.goal_seek || [];
  if (gs.length) {
    const need = gs.filter((g) => g.status === 'threshold_found' && Number.isFinite(g.value) && g.value > 0).sort((a, b) => b.value - a.value);
    const no = gs.filter((g) => g.status === 'not_reached_within_bounds');
    const ok = gs.filter((g) => g.status === 'already_satisfied' || (g.status === 'threshold_found' && g.value === 0));
    if (need.length) cards.push({ key: 'goal', title: L.cGoal, big: chf(need[0].value), text: L.cGoalNeed(L.q(need[0].goal), month1(need[0].to_month) ?? '–'), tone: 'warn',
      more: [...need.slice(1).map((g) => `${chf(g.value)} ${L.cGoalNeed(L.q(g.goal), month1(g.to_month) ?? '–')}`), ...ok.map((g) => L.cGoalOk(g.goal)), ...no.map((g) => L.cGoalNo(g.goal))] });
    else if (no.length) cards.push({ key: 'goal', title: L.cGoal, big: '–', text: L.cGoalNo(no.map((g) => g.goal).join(', ')), tone: 'bad', more: ok.map((g) => L.cGoalOk(g.goal)) });
    else cards.push({ key: 'goal', title: L.cGoal, big: chf(0), text: L.cGoalOk(ok.map((g) => g.goal).join(', ')), tone: 'good' });
  }
  const tm = (ex.timing || []).filter((x) => Number.isFinite(x.delta_final_net_worth));
  if (tm.length) {
    const t0 = tm[0];
    const short = (x) => (x.first_negative_month != null ? ri(lang).shortFrom(x.first_negative_month + 1) : L.cNeverShort);
    cards.push({ key: 'timing', title: L.cTime, big: signedChf(t0.delta_final_net_worth), text: L.cTimeLine(t0.delay_months, short(t0)), tone: t0.delta_final_net_worth >= 0 ? 'good' : 'bad',
      more: tm.slice(1).map((x) => `${signedChf(x.delta_final_net_worth)} ${L.cTimeLine(x.delay_months, short(x))}`) });
  }
  return cards;
}

// Tornado rows: the full sensitivity list when loaded, else the exploration levers. Nominal final net worth.
export function tornadoRows(step, max = 6) {
  const r = step?.result || {};
  const sens = Array.isArray(r.sensitivity) && r.sensitivity.length ? r.sensitivity : null;
  const src = sens || r.exploration?.levers || [];
  const base = sens?.[0]?.base_final_net_worth ?? r.metrics?.final_net_worth ?? r.deterministic?.final_net_worth;
  return src.filter((x) => Number.isFinite(x.final_net_worth_low) && Number.isFinite(x.final_net_worth_high)).slice(0, max).map((x) => ({
    id: x.assumption_id, label: x.label || x.assumption_id, unit: x.unit || '',
    base_value: x.base_value, low_value: x.low_value, high_value: x.high_value,
    low: x.final_net_worth_low, high: x.final_net_worth_high, base,
    swing: Math.abs(x.final_net_worth_high - x.final_net_worth_low),
  }));
}

export function stressRows(data, lang) {
  const L = ri(lang);
  return (data.stress || []).map((x) => {
    const s = x.summary || {};
    const holds = x.weather === 'none' ? s.first_negative_month == null && (s.goals_met ?? 0) >= (s.goals_total ?? 0) : !!s.holds;
    return { key: x.weather, name: L.weather[x.weather] || x.weather, holds, min_cash: s.min_cash, short: month1(s.first_negative_month), final_net_worth: s.final_net_worth };
  });
}

const pct = (v) => `${Math.round(v * 100)}%`;
export function constraintRows(constraints = [], lang) {
  const L = ri(lang);
  return constraints.map((c) => {
    const goal = c.name?.startsWith('goal:') ? c.name.slice(5) : null;
    const label = goal ? L.cons.goal(goal) : c.name === 'no_funding_gap' ? L.cons.no_funding_gap
      : c.name === 'debt_service_limit' ? L.cons.debt_service_limit(pct(c.threshold)) : c.name === 'liquidity_buffer' ? L.cons.liquidity_buffer(dec(c.threshold, 0)) : c.label || c.name;
    const ratioUnit = /income/.test(c.unit || '');
    const mg = c.margin;
    const margin = !Number.isFinite(mg) ? '–' : c.unit === 'CHF' || goal ? signedChf(mg) : ratioUnit ? `${mg >= 0 ? '+' : MINUS}${Math.round(Math.abs(mg) * 100)} ${L.pts}` : /month/.test(c.unit || '') ? `${mg >= 0 ? '+' : MINUS}${L.months(dec(Math.abs(mg)))}` : dec(mg, 2);
    const scale = Math.max(Math.abs(c.threshold || 0), Math.abs(c.value || 0), Math.abs(mg || 0), 1e-9);
    return { name: c.name, label, kind: c.kind, passed: !!c.passed, margin, ratio: Number.isFinite(mg) ? Math.max(-1, Math.min(1, mg / scale)) : 0,
      sub: !c.passed && c.first_breach_month != null ? L.breach(c.first_breach_month + 1, c.months_in_breach) : '' };
  });
}

const QUAL = [[/master|stud|scholar|graduat|internship|tuition|drop out/i, 'education'], [/abroad|zurich|lausanne|come back|move/i, 'location'],
  [/80%|60%|part-time|sabbatical|pause|side (job|project)|raise|promotion/i, 'time'], [/car\b/i, 'mobility'], [/share|shared|flat alone/i, 'space'],
  [/equit|invest|stay the course/i, 'risk'], [/loan|repay|credit/i, 'obligations']];
export const qualKeys = (data) => [...new Set(data.steps.flatMap((st) => QUAL.filter(([re]) => re.test(st.label)).map(([, k]) => k)))];

// Over-time chart series for the leaf level: the chosen path last so it draws on top.
export function timeSeries(data, metric = 'cash') {
  const key = metric === 'cash' ? 'cash' : 'net_worth';
  return [...(data.leaf?.peers || [])].sort((a, b) => Number(a.chosen) - Number(b.chosen))
    .map((p) => ({ id: p.node_id, label: p.label, description: p.description, chosen: p.chosen, values: p[key] || [] })).filter((s) => s.values.length > 1);
}

// Comparison rows for every step: the chosen option and its siblings, by real net worth after 10 years.
export function compareLevels(data) {
  return data.steps.map((st, i) => ({
    step: i + 1, node_id: st.node_id, label: st.label, description: st.description,
    rows: [{ node_id: st.node_id, label: st.label, description: st.description, chosen: true, ...st.summary },
      ...st.alternatives.map((a) => ({ node_id: a.node_id, label: a.label, description: a.description, chosen: false, ...a.summary }))],
  }));
}

// Where (and as what household) income is taxed, one line per stretch of months (core #48 item 3).
// A Lausanne fallback (no table for the user's place) is flagged, never hidden.
export function taxSegments(segments = [], lang = 'en', assumptions = []) {
  const L = ri(lang);
  const rateA = assumptions.find((a) => a.id === 'AS-tax-abroad-rate'), abroadRate = rateA?.value;
  return (segments || []).map((g) => {
    const months = Number.isFinite(g.from_month) && Number.isFinite(g.to_month) ? L.taxMonths(g.from_month + 1, g.to_month) : '';
    if (g.taxed === false) return { key: `${g.from_month}-none`, place: L.taxNone, household: '', months, fallback: false, abroad: false };
    const abroad = !!g.country && g.country !== 'CH';
    return {
      key: `${g.from_month}-${g.city || g.country}`, months, abroad, fallback: !!g.fallback, unverified: abroad && rateA?.verified === false,
      place: abroad ? L.taxAbroad(Number.isFinite(abroadRate) ? `${Math.round(abroadRate * 1000) / 10}%` : '') : L.taxCH(g.city || 'Lausanne', g.canton),
      household: L.household[g.household] || g.household || '',
    };
  });
}

// Pillar 3a (core #48 item 4): the same money paid into 3a, invested or kept in cash, for one step.
// null when the engine did not return it (older engine or exploration not loaded): the card is not drawn.
// Never ranks the options: the bars show net worth split into liquid and locked, and the caveat says why.
export function pillar3a(step, lang = 'en') {
  const L = ri(lang), p = step?.result?.exploration?.pillar_3a;
  if (!p || typeof p !== 'object') return null;
  if (p.status === 'no_earned_income') return { status: 'no_earned_income', text: L.p3NoIncome, rows: [] };
  const opts = Array.isArray(p.options) ? p.options : [];
  if (!opts.length) return null;
  const order = ['keep_in_cash', 'pay_into_3a', 'invest'];
  const rows = [...opts].sort((a, b) => order.indexOf(a.option) - order.indexOf(b.option)).map((o) => ({
    key: o.option, label: L.p3Opt[o.option] || o.option, nw: o.final_net_worth, liquid: o.final_liquid,
    locked: o.final_pillar_3a || 0, minCash: o.min_cash, gap: Number.isFinite(o.min_cash) && o.min_cash < 0, taxSaved: o.tax_saved_by_3a || 0,
  }));
  const into = rows.find((r) => r.key === 'pay_into_3a');
  const seek = p.max_monthly_3a_keeping_goals || {};
  const seekFn = L.p3Seek[seek.status];
  const monthly = Number.isFinite(p.monthly_amount) ? chf(p.monthly_amount) : '–';
  return {
    status: p.status || 'evaluated', rows,
    lead: L.p3Lead(monthly, Number.isFinite(p.annual_cap) ? chf(p.annual_cap) : '–'),
    caveat: into && into.locked > 0 ? L.p3Caveat(chf(into.taxSaved), chf(into.liquid), chf(into.locked)) : '',
    seek: seekFn ? seekFn(Number.isFinite(seek.value) ? chf(seek.value) : monthly) : '',
  };
}
