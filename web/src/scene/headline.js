// Branch cards and the plan check (docs/report-spec.md §1-2, engine core-1.2 `result.headline`,
// `result.plan_check`, `result.constraints`). Texts are rebuilt from the structured fields so they
// follow the UI language; an unknown metric falls back to the engine's English text.

const chf = (n) => (Number.isFinite(n) ? (n < 0 ? '−' : '') + 'CHF ' + Math.abs(Math.round(n)).toLocaleString('en-US').replace(/,/g, '’') : '–');
const dec = (n, d = 1) => (Number.isFinite(n) ? (Math.round(n * 10 ** d) / 10 ** d).toString() : '–');
const signed = (s, n) => (n > 0 ? '+' : n < 0 ? '−' : '±') + s;

export const H_I18N = {
  en: {
    gap: (v, m) => `Funding gap ${chf(v)} from month ${m}`, missed: (g, v) => `${g} missed by ${chf(v)}`, buffer: (v, m) => `Tightest buffer: ${dec(v)} months (month ${m})`,
    metric: { final_net_worth_real: "Net worth after 10 years (today's prices)", final_net_worth: 'Net worth after 10 years', min_cash: 'Lowest cash', liquidity_months: 'Tightest buffer', final_debt: 'Debt after 10 years', earliest_goal_month: 'First goal reached' },
    months: (v) => `${dec(v)} months`, monthN: (v) => `month ${v}`, vsParent: (d) => `${d} vs before this choice`, vsNeutral: (d) => `${d} vs the neutral outlook`, sameNeutral: 'same as the neutral outlook', same: 'same as before this choice', none: 'none',
    level: { needs_financing: 'Needs financing', infeasible: 'Does not hold: a limit is broken', holds_below_target: 'Holds, below the buffer target', holds: 'Holds' },
    planCheck: 'Plan check', holdsWeather: (h, o) => `Holds in ${h} of ${o} stress scenarios`, shock: (v) => `absorbs a surprise cost of up to ${chf(v)}`, shockBroken: 'no room for a surprise cost',
    constraints: 'Limits and targets', pass: 'passes', fail: 'breached', margin: 'margin', breach: (m, n) => `from month ${m}, ${n} months in breach`,
    kind: { hard: 'hard limit', target: 'target', goal: 'goal' }, score: (s) => `Secondary score: ${Math.round(s)} / 100 (weights are a value judgement, shown openly)`,
  },
  es: {
    gap: (v, m) => `Falta financiación de ${chf(v)} desde el mes ${m}`, missed: (g, v) => `${g}: faltan ${chf(v)}`, buffer: (v, m) => `Colchón mínimo: ${dec(v)} meses (mes ${m})`,
    metric: { final_net_worth_real: 'Patrimonio a 10 años (precios de hoy)', final_net_worth: 'Patrimonio a 10 años', min_cash: 'Liquidez mínima', liquidity_months: 'Colchón mínimo', final_debt: 'Deuda a 10 años', earliest_goal_month: 'Primer objetivo alcanzado' },
    months: (v) => `${dec(v)} meses`, monthN: (v) => `mes ${v}`, vsParent: (d) => `${d} respecto a antes de esta decisión`, vsNeutral: (d) => `${d} respecto a la perspectiva neutral`, sameNeutral: 'igual que con la perspectiva neutral', same: 'igual que antes de esta decisión', none: 'ninguno',
    level: { needs_financing: 'Necesita financiación', infeasible: 'No se sostiene: se rompe un límite', holds_below_target: 'Se sostiene, por debajo del colchón objetivo', holds: 'Se sostiene' },
    planCheck: 'Revisión del plan', holdsWeather: (h, o) => `Se sostiene en ${h} de ${o} escenarios de estrés`, shock: (v) => `aguanta un imprevisto de hasta ${chf(v)}`, shockBroken: 'sin margen para un imprevisto',
    constraints: 'Límites y objetivos', pass: 'se cumple', fail: 'se incumple', margin: 'margen', breach: (m, n) => `desde el mes ${m}, ${n} meses incumplido`,
    kind: { hard: 'límite', target: 'objetivo', goal: 'meta' }, score: (s) => `Puntuación secundaria: ${Math.round(s)} / 100 (los pesos son un juicio de valor, a la vista)`,
  },
  fr: {
    gap: (v, m) => `Besoin de financement de ${chf(v)} dès le mois ${m}`, missed: (g, v) => `${g} manqué de ${chf(v)}`, buffer: (v, m) => `Coussin le plus bas : ${dec(v)} mois (mois ${m})`,
    metric: { final_net_worth_real: "Patrimoine dans 10 ans (prix d'aujourd'hui)", final_net_worth: 'Patrimoine dans 10 ans', min_cash: 'Trésorerie minimale', liquidity_months: 'Coussin le plus bas', final_debt: 'Dette dans 10 ans', earliest_goal_month: 'Premier objectif atteint' },
    months: (v) => `${dec(v)} mois`, monthN: (v) => `mois ${v}`, vsParent: (d) => `${d} par rapport à avant ce choix`, vsNeutral: (d) => `${d} par rapport à la perspective neutre`, sameNeutral: 'comme avec la perspective neutre', same: 'comme avant ce choix', none: 'aucun',
    level: { needs_financing: 'A besoin de financement', infeasible: 'Ne tient pas : une limite est franchie', holds_below_target: 'Tient, sous le coussin visé', holds: 'Tient' },
    planCheck: 'Contrôle du plan', holdsWeather: (h, o) => `Tient dans ${h} scénarios de stress sur ${o}`, shock: (v) => `encaisse un imprévu jusqu'à ${chf(v)}`, shockBroken: "pas de marge pour un imprévu",
    constraints: 'Limites et objectifs', pass: 'respecté', fail: 'non respecté', margin: 'marge', breach: (m, n) => `dès le mois ${m}, ${n} mois hors limite`,
    kind: { hard: 'limite', target: 'cible', goal: 'objectif' }, score: (s) => `Score secondaire : ${Math.round(s)} / 100 (les pondérations sont un jugement de valeur, affichées)`,
  },
  de: {
    gap: (v, m) => `Finanzierungslücke ${chf(v)} ab Monat ${m}`, missed: (g, v) => `${g} um ${chf(v)} verfehlt`, buffer: (v, m) => `Knappster Puffer: ${dec(v)} Monate (Monat ${m})`,
    metric: { final_net_worth_real: 'Vermögen nach 10 Jahren (heutige Preise)', final_net_worth: 'Vermögen nach 10 Jahren', min_cash: 'Tiefste Liquidität', liquidity_months: 'Knappster Puffer', final_debt: 'Schulden nach 10 Jahren', earliest_goal_month: 'Erstes Ziel erreicht' },
    months: (v) => `${dec(v)} Monate`, monthN: (v) => `Monat ${v}`, vsParent: (d) => `${d} gegenüber vor dieser Entscheidung`, vsNeutral: (d) => `${d} gegenüber der neutralen Perspektive`, sameNeutral: 'gleich wie bei neutraler Perspektive', same: 'gleich wie vor dieser Entscheidung', none: 'keines',
    level: { needs_financing: 'Braucht Finanzierung', infeasible: 'Hält nicht: eine Grenze wird verletzt', holds_below_target: 'Hält, unter dem Pufferziel', holds: 'Hält' },
    planCheck: 'Plan-Check', holdsWeather: (h, o) => `Hält in ${h} von ${o} Stressszenarien`, shock: (v) => `verträgt unerwartete Kosten bis ${chf(v)}`, shockBroken: 'kein Spielraum für unerwartete Kosten',
    constraints: 'Grenzen und Ziele', pass: 'eingehalten', fail: 'verletzt', margin: 'Spielraum', breach: (m, n) => `ab Monat ${m}, ${n} Monate verletzt`,
    kind: { hard: 'harte Grenze', target: 'Zielwert', goal: 'Ziel' }, score: (s) => `Sekundärer Wert: ${Math.round(s)} / 100 (Gewichte sind ein Werturteil und offen gezeigt)`,
  },
};

function fmtByUnit(v, unit, L) {
  if (!Number.isFinite(v)) return L.none;
  if (unit === 'CHF') return chf(v);
  if (unit === 'months') return L.months(v);
  if (unit === 'month') return L.monthN(v + 1);
  return dec(v, 2);
}

// The two card slots in the UI language: {a: {kind, text}, b: {text, vs}}; null when not available.
export function cardHeadline(result, lang = 'en') {
  const L = H_I18N[lang] || H_I18N.en, h = result?.headline;
  if (!h) return fallbackHeadline(result, L);
  const A = h.slot_a, B = h.slot_b;
  let a = null;
  if (A) {
    const m = Number.isFinite(A.month) ? A.month + 1 : null;
    a = { kind: A.kind, text: A.kind === 'funding_gap' ? L.gap(A.value, m) : A.kind === 'goal_missed' ? (A.goal ? L.missed(A.goal, A.value) : A.text)
      : A.kind === 'tightest_buffer' ? L.buffer(A.value, m) : A.text };
  }
  let b = null;
  if (B) {
    const label = L.metric[B.metric];
    const text = label ? `${label}: ${fmtByUnit(B.value, B.unit, L)}` : B.text;
    let vs = '';
    if (label && B.vs_neutral != null) { // #103: a macro outlook is on: how much it moves this card
      const d = B.vs_neutral;
      vs = Math.abs(d) < 0.5 ? L.sameNeutral : L.vsNeutral(signed(chf(Math.abs(d)), d));
    } else if (label && B.vs_parent != null) {
      const d = B.vs_parent;
      const mag = B.unit === 'CHF' ? chf(Math.abs(d)) : B.unit === 'months' ? L.months(Math.abs(d)) : B.unit === 'month' ? L.months(Math.abs(d)) : dec(Math.abs(d), 2);
      vs = Math.abs(d) < 1e-9 ? L.same : L.vsParent(signed(mag, d));
    } else if (!label) vs = B.vs_parent_text || '';
    b = { text, vs, metric: B.metric };
  }
  return { a, b };
}

// Before core-1.2: same rule as slot A from the existing metrics (no slot B).
function fallbackHeadline(r, L) {
  const m = r?.metrics;
  if (!m) return null;
  if (m.first_negative_month != null) return { a: { kind: 'funding_gap', text: L.gap(-m.min_cash, m.first_negative_month + 1) }, b: null };
  if (Number.isFinite(m.liquidity_months)) return { a: { kind: 'tightest_buffer', text: L.buffer(m.liquidity_months, (m.min_cash_month ?? 0) + 1) }, b: null };
  return null;
}

// Plan check, feasibility first. A funding gap always reads "needs financing", never as a fine score.
export function planCheck(result, lang = 'en') {
  const L = H_I18N[lang] || H_I18N.en, pc = result?.plan_check;
  if (pc) return { level: pc.level, label: L.level[pc.level] || pc.label, feasible: pc.feasible, resilience: pc.resilience, score: pc.score };
  const m = result?.metrics; // fallback before core-1.2
  if (m?.first_negative_month != null) return { level: 'needs_financing', label: L.level.needs_financing, feasible: false };
  return m ? { level: 'holds', label: L.level.holds, feasible: true, score: result?.health?.score } : null;
}

export function planCheckHTML(result, lang = 'en', esc = (s) => s) {
  const L = H_I18N[lang] || H_I18N.en, pc = planCheck(result, lang);
  if (!pc) return '';
  const r = pc.resilience, parts = [];
  if (r) {
    if (r.of) parts.push(L.holdsWeather(r.holds_in_weather ?? 0, r.of));
    if (r.shock_buffer_status === 'already_broken' || (pc.level === 'needs_financing' && !r.shock_buffer_chf)) parts.push(L.shockBroken);
    else if (Number.isFinite(r.shock_buffer_chf)) parts.push(L.shock(r.shock_buffer_chf));
  }
  const rows = (result.constraints || []).map((c) => {
    const unit = c.unit === 'CHF' ? chf : (v) => dec(v, 2);
    const breach = !c.passed && c.first_breach_month != null ? ` · ${L.breach(c.first_breach_month + 1, c.months_in_breach)}` : '';
    return `<li class="${c.passed ? 'ok' : 'bad'}"><span class="pf">${c.passed ? '✓' : '✕'}</span><span><b>${esc(c.label || c.name)}</b>
      <small>${L.kind[c.kind] || c.kind} · ${c.passed ? L.pass : L.fail} · ${L.margin} ${unit(c.margin)}${breach}</small></span></li>`;
  }).join('');
  return `<div class="plan-check ${pc.level}"><div class="pc-head"><span class="pc-kicker">${L.planCheck}</span><b>${esc(pc.label)}</b>
    ${parts.length ? `<span class="pc-sub">${parts.join(' · ')}</span>` : ''}</div>
    ${rows ? `<h4>${L.constraints}</h4><ul class="constraints">${rows}</ul>` : ''}
    ${Number.isFinite(pc.score) ? `<p class="note">${L.score(pc.score)}</p>` : ''}</div>`;
}
