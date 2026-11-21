// Pure derivations of the comparison (no network, no DOM; runs under `node --test`). Every number is
// read from engine fields (/tree/expand, /tree/explore, /tree/smallest_change, /tree/timing_scan or
// /tree/compare); nothing is estimated here. Never ranks anything as "best": rows mark highest and lowest.
import { ci, chf, chfK, signed } from './i18n.js';

export const MAX_COMPARE = 4;
export const LEVEL_ORDER = ['holds', 'holds_below_target', 'infeasible', 'needs_financing'];
export const levelTone = (level) => (level === 'holds' ? 'good' : level === 'holds_below_target' ? 'warn' : level ? 'bad' : 'none');
const fin = Number.isFinite;
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

export const levelOf = (r) => r?.plan_check?.level || (r?.metrics ? (r.metrics.first_negative_month != null ? 'needs_financing' : 'holds') : null);
const metricOf = (r, metric) => {
  const m = r?.metrics || {};
  if (metric === 'final_net_worth_real') return fin(m.final_net_worth_real) ? m.final_net_worth_real : m.final_net_worth;
  return m[metric];
};

// ---------------------------------------------------------------- cards: options against each other
// The options a card is compared with: nodes sharing its parent that carry a result (children of the
// current node, or the current node and its siblings). `nodes` = the expand's `nodes` list.
export function optionGroup(nodes = [], nodeId) {
  const me = nodes.find((n) => n.node_id === nodeId);
  if (!me || me.node_id === '0') return [];
  return nodes.filter((n) => n.parent_id === me.parent_id && n.result && (n.status === 'child' || n.status === 'sibling' || n.is_current || n.status === 'chosen'));
}

/**
 * Where each option sits among its peers on one metric (default: real net worth in 10 years).
 * Returns {node_id: {value, rank (1 = highest), n, pos (0..1 on the shared scale), peers: [{node_id, pos}],
 * level, tone, gap, chips: [{kind, ...}]}}. Higher is not "better": the scale is just the value.
 */
export function compareSiblings(nodes = [], { metric = 'final_net_worth_real' } = {}) {
  const out = {};
  const groups = new Map();
  for (const n of nodes) {
    if (!n?.result || n.node_id === '0') continue;
    if (!(n.status === 'child' || n.status === 'sibling' || n.is_current)) continue;
    const k = n.parent_id ?? '?';
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(n);
  }
  for (const group of groups.values()) {
    const rows = group.map((n) => ({ node: n, v: metricOf(n.result, metric), gap: n.result?.metrics?.first_negative_month != null, level: levelOf(n.result) }));
    const vals = rows.map((r) => r.v).filter(fin);
    const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo;
    const posOf = (v) => (!fin(v) ? null : span > 0 ? (v - lo) / span : 0.5);
    for (const r of rows) {
      const others = rows.filter((o) => o !== r);
      const rank = fin(r.v) ? 1 + rows.filter((o) => fin(o.v) && o.v > r.v + 0.5).length : null;
      // plain meaning of the position (#103): highest / lowest / in the middle / same as the others
      const finite = rows.filter((o) => fin(o.v));
      const place = !fin(r.v) ? null : span <= 0.5 ? 'same'
        : rank === 1 ? 'highest' : !finite.some((o) => o.v < r.v - 0.5) ? 'lowest' : 'middle';
      const chips = [];
      // metric delta: the highest option vs the next one down, every other option vs the highest
      const ranked = others.filter((o) => fin(o.v)).sort((a, b) => b.v - a.v);
      if (fin(r.v) && ranked.length) {
        const peer = ranked[0];
        const d = r.v - peer.v;
        chips.push({ kind: Math.abs(d) < 500 ? 'same' : 'delta', metric, delta: d, peer_id: peer.node.node_id, peer_label: peer.node.label, tone: d > 0.5 ? 'up' : d < -0.5 ? 'down' : 'flat' });
      }
      // funding gap against the others
      const othersNoGap = others.filter((o) => !o.gap).length, othersGap = others.filter((o) => o.gap).length;
      if (r.gap && othersNoGap) chips.push({ kind: 'gap_vs_none', count: othersNoGap, tone: 'bad' });
      else if (!r.gap && othersGap) chips.push({ kind: 'no_gap_vs', count: othersGap, tone: 'good' });
      out[r.node.node_id] = {
        value: r.v, rank, place, n: rows.length, pos: posOf(r.v), level: r.level, tone: levelTone(r.level), gap: r.gap, metric,
        peers: others.map((o) => ({ node_id: o.node.node_id, pos: posOf(o.v), tone: levelTone(o.level) })), chips,
      };
    }
  }
  return out;
}

/** "Highest net worth of these 3" / "In the middle of these 3" / … in the UI language (#103). */
export function placeLabel(c, lang = 'en') {
  const L = ci(lang);
  if (!c?.place) return '';
  return L.place(c.place, c.n, L.noun[c.metric] || L.noun.final_net_worth_real);
}

// Chip text in the UI language; `tr` translates a node label ({label} → {label}).
export function chipText(chip, lang = 'en', label = (id, l) => l) {
  const L = ci(lang);
  if (chip.kind === 'delta') return L.vs(signed(chip.delta, chfK), label(chip.peer_id, chip.peer_label));
  if (chip.kind === 'same') return L.sameAs(label(chip.peer_id, chip.peer_label));
  if (chip.kind === 'gap_vs_none') return L.gapVsNone(chip.count);
  if (chip.kind === 'no_gap_vs') return L.noGapVs(chip.count);
  return '';
}

/**
 * The card strip as HTML (the scene's cards are HTML strings): a dot on a shared scale among the
 * peers + 1–2 chips. `compact` (phones) keeps the scale and one chip. Empty string when the node has
 * no peers to compare with.
 */
/**
 * The position strip on option cards is off by default (Juan, #103 follow-up): cards keep only the
 * "+" pin, and the position and deltas live in the comparison view. Opt in with `?strip=1` or
 * localStorage `cigala.compare.cardStrip` = '1'.
 */
export const CARD_STRIP_KEY = 'cigala.compare.cardStrip';
export function cardStripEnabled({ search = globalThis.location?.search || '', storage = globalThis.localStorage } = {}) {
  const q = new URLSearchParams(search).get('strip');
  if (q === '0' || q === '1') return q === '1';
  try { return storage?.getItem(CARD_STRIP_KEY) === '1'; } catch { return false; }
}

export function cardCompareHTML(node, nodes, { lang = 'en', label = (id, l) => l, metric = 'final_net_worth_real', compact = false, cmp } = {}) {
  const c = (cmp || compareSiblings(nodes, { metric }))[node?.node_id];
  if (!c || c.n < 2 || c.pos == null) return '';
  const L = ci(lang);
  const pct = (p) => `${(4 + p * 92).toFixed(1)}%`;
  const peers = c.peers.filter((p) => p.pos != null).map((p) => `<i class="ccs-peer ${p.tone}" style="left:${pct(p.pos)}"></i>`).join('');
  const placeText = placeLabel(c, lang);
  const aria = L.scaleLabel(L.metric[metric] || metric, chfK(c.value), placeText);
  const chips = (compact ? c.chips.slice(0, 1) : c.chips.slice(0, 2))
    .map((ch) => `<span class="ccs-chip ${ch.tone}">${ch.kind === 'gap_vs_none' ? '<b aria-hidden="true">✕</b>' : ch.kind === 'no_gap_vs' ? '<b aria-hidden="true">✓</b>' : ''}${esc(chipText(ch, lang, label))}</span>`).join('');
  return `<span class="ccs ${c.tone}${compact ? ' compact' : ''}"><span class="ccs-scale" role="img" aria-label="${esc(aria)}">`
    + `<span class="ccs-track"></span>${peers}<i class="ccs-me ${c.tone}" style="left:${pct(c.pos)}"></i>`
    + `<span class="ccs-rank" aria-hidden="true">${esc(placeText)}</span></span>`
    + (chips ? `<span class="ccs-chips">${chips}</span>` : '') + '</span>';
}

// ---------------------------------------------------------------- which paths to compare
// "Compare these options": the current node's children; on a leaf, the node and its siblings.
// Paths are node ids from the root, without "0" (the /tree/expand convention).
export function optionPaths(tree) {
  if (!tree?.nodes) return [];
  const chosen = (tree.path || []).filter((id) => id !== '0');
  const kids = tree.nodes.filter((n) => n.status === 'child');
  if (kids.length) return kids.map((n) => [...chosen, n.node_id]);
  const cur = tree.current;
  if (!cur || cur === '0') return [];
  const base = chosen.slice(0, -1);
  const sibs = tree.nodes.filter((n) => n.node_id === cur || n.status === 'sibling');
  return sibs.map((n) => [...base, n.node_id]);
}
export const pathKey = (p = []) => p.filter((id) => id !== '0').join('/') || '0';

// ---------------------------------------------------------------- the comparison table
/**
 * A column (one path), as produced by data.js (from /tree/compare or the expand fallback):
 * {key, path, node_id, label, crumbs: [{id,label}], result, parent: {node_id,label,result}|null,
 *  baseline: result of "0", exploration, smallest, timing, assumptions: [{id,label,unit,value}],
 *  personal: [{label, kind}], peers_in_columns}
 */
const goalsMet = (r) => {
  if (Array.isArray(r?.goals)) return { met: r.goals.filter((x) => x.met_deterministic).length, total: r.goals.length };
  const m = r?.metrics || {};
  return { met: m.goals_met ?? null, total: m.goals_total ?? null };
};
const holdsIn = (r) => { const w = r?.weather_resilience || r?.plan_check?.resilience; if (!w) return null; return { h: w.holds_in ?? w.holds_in_weather ?? 0, of: w.of ?? 0 }; };
const fixValue = (s, lever) => s?.changes?.find((c) => c.lever === lever);

function numRow(key, label, cols, get, fmt, opts = {}) {
  const cells = cols.map((c) => { const v = get(c); return { value: fin(v) ? v : null, text: fin(v) ? fmt(v, c) : (opts.empty ? opts.empty(c) : '–') }; });
  return { key, label, cells, numeric: true, ...opts };
}
function textRow(key, label, cols, get, opts = {}) {
  return { key, label, cells: cols.map((c) => { const t = get(c); return typeof t === 'object' && t ? t : { text: t ?? '–' }; }), ...opts };
}

// mark highest / lowest on numeric rows with at least two distinct values
export function markExtremes(row) {
  if (!row.numeric) return row;
  const vals = row.cells.map((c) => c.value).filter(fin);
  if (vals.length < 2) return row;
  const hi = Math.max(...vals), lo = Math.min(...vals);
  if (Math.abs(hi - lo) < (row.tol ?? 0.5)) return row;
  return { ...row, cells: row.cells.map((c) => (!fin(c.value) ? c : { ...c, mark: Math.abs(c.value - hi) < 1e-9 ? 'hi' : Math.abs(c.value - lo) < 1e-9 ? 'lo' : null })) };
}
export const rowDiffers = (row) => new Set(row.cells.map((c) => c.text)).size > 1;

export function buildComparison(cols = [], { lang = 'en', label = (id, l) => l, weatherLabel = (t) => t } = {}) {
  const L = ci(lang);
  const name = (c) => label(c.node_id, c.label);
  const sections = [];
  const sec = (key, rows) => { const r = rows.filter(Boolean).map(markExtremes); if (r.length) sections.push({ key, title: L.sec[key], rows: r }); };

  sec('outcome', [
    textRow('plan', L.r.plan, cols, (c) => { const lv = levelOf(c.result); return { text: c.planLabel || lv || '–', level: lv, tone: levelTone(lv) }; }),
    numRow('nw', L.r.nw, cols, (c) => metricOf(c.result, 'final_net_worth_real'), (v) => chf(v)),
    numRow('low', L.r.low, cols, (c) => c.result?.metrics?.min_cash, (v, c) => L.lowAt(chf(v), (c.result.metrics.min_cash_month ?? 0) + 1)),
    numRow('gap', L.r.gap, cols, (c) => (c.result?.metrics ? Math.max(0, -(c.result.metrics.min_cash ?? 0)) : null),
      (v, c) => (v > 0.5 ? L.gapFrom(chf(v), (c.result.metrics.first_negative_month ?? 0) + 1) : L.none)),
    numRow('goals', L.r.goals, cols, (c) => goalsMet(c.result).met, (v, c) => L.goalsOf(v, goalsMet(c.result).total), { tol: 0.5 }),
    numRow('liq', L.r.liq, cols, (c) => c.result?.metrics?.liquidity_months, (v) => L.months(String(Math.round(v * 10) / 10).replace('-', '−')), { tol: 0.05 }),
    numRow('debt', L.r.debt, cols, (c) => c.result?.metrics?.final_debt, (v) => chf(v)),
  ]);

  const nwOf = (r) => metricOf(r, 'final_net_worth_real');
  // "this choice alone": the server's impact_alone deltas, else this result minus its parent's / today's
  const dParent = (c, k, own) => (c.impact?.vs_parent?.delta ? c.impact.vs_parent.delta[k] : c.parent?.result ? own(c.result) - own(c.parent.result) : null);
  const dToday = (c) => (c.node_id === '0' ? null : c.impact?.vs_today?.delta ? c.impact.vs_today.delta.final_net_worth_real : c.baseline ? nwOf(c.result) - nwOf(c.baseline) : null);
  sec('impact', [
    numRow('vsParent', L.r.vsParent, cols, (c) => dParent(c, 'final_net_worth_real', nwOf), (v) => signed(v), { empty: () => L.noParent }),
    numRow('lowVsParent', L.r.lowVsParent, cols, (c) => dParent(c, 'min_cash', (r) => r.metrics.min_cash), (v) => signed(v), { empty: () => L.noParent }),
    numRow('goalsVsParent', L.r.goalsVsParent, cols, (c) => dParent(c, 'goals_met', (r) => goalsMet(r).met), (v) => L.goalsDelta(Math.round(v)), { empty: () => L.noParent, tol: 0.5 }),
    numRow('vsToday', L.r.vsToday, cols, dToday, (v) => signed(v), { empty: () => L.rootDelta }),
  ]);

  const anyTruth = cols.some((c) => c.smallest || c.timing || c.exploration);
  if (anyTruth) {
    const fixText = (s, lever, f) => {
      if (!s) return null;
      if (s.already_holds) return { text: L.alreadyHolds, value: 0 };
      const ch = fixValue(s, lever);
      if (!ch) return null;
      if (ch.status === 'threshold_found' && fin(ch.value)) return { text: f(chf(ch.value)), value: ch.value };
      if (ch.status === 'already_satisfied') return { text: L.alreadyHolds, value: 0 };
      return { text: L.notWithin, value: null };
    };
    const fix = textRow('fix', L.r.fix, cols, (c) => fixText(c.smallest, 'more_income', L.perMonth) || { text: '–' });
    const cashNow = textRow('cashNow', L.r.cashNow, cols, (c) => fixText(c.smallest, 'cash_now', L.cashNowV) || { text: '–' });
    fix.numeric = cashNow.numeric = true;
    const timing = textRow('timing', L.r.timing, cols, (c) => {
      const t = c.timing;
      if (!t) return '–';
      if (t.status === 'no_own_decision') return L.timingNA;
      const rows = t.rows || [];
      const first = rows.find((r) => r.feasible);
      if (fin(t.latest_start_that_holds) && rows[0]?.feasible) return L.timingAll(t.latest_start_that_holds);
      if (first) return L.timingFrom(first.delay_months + 1);
      return L.timingNone;
    });
    const keys = new Set(cols.map((c) => c.node_id));
    const be = textRow('breakEven', L.r.breakEven, cols, (c) => {
      const rows = c.exploration?.break_even || [];
      const r = rows.find((x) => keys.has(x.compared_to)) || null;
      if (!r) return '–';
      const who = label(r.compared_to, r.label);
      const sal = r.salary_threshold?.status === 'threshold_found' && fin(r.salary_threshold.value) ? ` · ${L.beSalary(chf(r.salary_threshold.value))}` : '';
      return L.beAhead(signed(r.delta_final_net_worth), who) + sal;
    });
    sec('truth', [fix, cashNow, timing, be]);
  }

  sec('stress', [
    numRow('stress', L.r.stress, cols, (c) => holdsIn(c.result)?.h, (v, c) => L.holdsIn(v, holdsIn(c.result).of), { tol: 0.5 }),
    textRow('breaks', L.r.breaks, cols, (c) => {
      const by = c.result?.weather_resilience?.by_weather || [];
      const b = by.filter((w) => w.holds === false).map((w) => weatherLabel(w.type));
      return b.length ? b.join(', ') : L.none;
    }),
  ]);

  // assumptions whose value differs between columns (from each result's assumptions_used)
  const used = cols.map((c) => new Map((c.result?.assumptions_used || []).map((a) => [a.id, a.value])));
  const ids = [...new Set(used.flatMap((m) => [...m.keys()]))];
  const meta = new Map(cols.flatMap((c) => c.assumptions || []).map((a) => [a.id, a]));
  const diff = ids.filter((id) => new Set(used.map((m) => JSON.stringify(m.get(id) ?? null))).size > 1).slice(0, 10);
  sec('assumptions', diff.map((id) => {
    const a = meta.get(id) || {};
    return textRow(`as:${id}`, a.label || id, cols, (c) => {
      const v = used[cols.indexOf(c)].get(id);
      return v == null ? '–' : fmtAssumption(v, a.unit);
    });
  }));

  const anyPersonal = cols.some((c) => c.personal?.length);
  if (anyPersonal) sec('personal', [textRow('personal', L.sec.personal, cols, (c) => (c.personal?.length ? c.personal.map((p) => p.label).join(' · ') : L.noConditions))]);

  return { columns: cols.map((c) => ({ key: c.key, node_id: c.node_id, label: name(c), crumbs: c.crumbs || [], level: levelOf(c.result), tone: levelTone(levelOf(c.result)) })), sections };
}

export function fmtAssumption(v, unit = '') {
  if (!fin(v)) return typeof v === 'object' ? JSON.stringify(v) : String(v);
  if (/^1\/year$|^share/.test(unit) || (Math.abs(v) < 1 && !/CHF/.test(unit) && unit !== 'multiplier')) return `${Math.round(v * 1000) / 10}%`;
  if (unit === 'multiplier') return `×${Math.round(v * 100) / 100}`;
  if (/^CHF|EUR/.test(unit)) return `${chf(v).replace('CHF', /^EUR/.test(unit) ? 'EUR' : 'CHF')}${unit.replace(/^(CHF|EUR)/, '')}`;
  return `${Math.round(v * 100) / 100}${unit ? ' ' + unit : ''}`;
}

export const onlyDifferences = (sections) => sections.map((s) => ({ ...s, rows: s.rows.filter(rowDiffers) })).filter((s) => s.rows.length);

// series for the overlay chart: one line per column (today's prices for net worth, nominal cash)
export function seriesOf(cols, which = 'net_worth_real') {
  return cols.map((c, i) => {
    const d = c.result?.deterministic || {};
    const values = (which === 'cash' ? d.cash : d.net_worth_real?.length ? d.net_worth_real : d.net_worth) || [];
    return { key: c.key, slot: i, label: c.label, node_id: c.node_id, values };
  });
}
