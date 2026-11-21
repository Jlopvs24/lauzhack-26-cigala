// "What would have to be true": core-1.1 `result.exploration` as plain sentences (EN/ES/FR/DE).
// Every analysis is deterministic: "if these inputs hold, then ...". A null value is never shown as a
// number; its status is said in words. Lever buttons carry data-lever/data-value for a recompute.

const chf = (n) => (n == null || !Number.isFinite(n) ? '–' : (n < 0 ? '−' : '') + 'CHF ' + Math.abs(Math.round(n)).toLocaleString('en-US').replace(/,/g, '’'));
const num = (n) => (Number.isFinite(n) ? (Math.abs(n) >= 1000 ? Math.round(n).toLocaleString('en-US').replace(/,/g, '’') : String(Math.round(n * 100) / 100)) : '–');
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
// unit-aware value: rates per year as %, multipliers as ×, money/other with the unit after it
const fmtVal = (v, unit = '') => {
  if (!Number.isFinite(v)) return '–';
  if (/^1\/year$|^share/.test(unit)) return `${Math.round(v * 1000) / 10}%`;
  if (unit === 'multiplier') return `×${Math.round(v * 100) / 100}`;
  return `${num(v)}${unit ? ' ' + unit : ''}`;
};
const month = (i) => (Number.isFinite(i) ? i + 1 : null); // engine months are 0-based

export const EX_I18N = {
  en: {
    title: 'What would have to be true', condition: 'If these inputs hold, these consequences follow under the stated assumptions. Each line changes one thing and keeps the rest fixed.',
    stressTitle: 'How much of a surprise can this plan absorb?',
    broken: (m, low) => `<b>Cash already runs short in this scenario</b>${m ? ` from month ${m}` : ''}${low ? ` (lowest ${low})` : ''}, even with no surprise cost. Under these assumptions the plan needs extra money or a change.`,
    absorbs: (v) => `It absorbs a surprise cost of up to <b>${v}</b> today before cash runs short or a dated goal is missed.`,
    unbreakable: (v) => `Even a surprise cost of ${v} today would not break it.`,
    leversTitle: 'The assumptions that move this branch most',
    lever: (l, base, u, lo, nwlo, hi, nwhi) => `<b>${l}</b> (now ${base}): at ${lo} net worth in 10 years is ${nwlo}; at ${hi} it is ${nwhi}.`,
    shortAt: 'cash runs short', tryV: (v) => `Try ${v}`,
    beTitle: 'Compared with the other options',
    ahead: (l, d) => `Ends <b>${d} ahead</b> of “${l}” after 10 years.`, behind: (l, d) => `Ends <b>${d} behind</b> “${l}” after 10 years.`,
    crossover: (m) => ` It moves ahead for good from month ${m}.`, aheadAll: ' It is ahead from the start.', neverAhead: ' It never stays ahead.',
    sal: (l, v, u) => ` Both end level if ${l} is <b>${v} ${u}</b>.`,
    goalTitle: 'What it would take to reach each goal',
    goalNeed: (g, v, m) => `<b>${g}</b>: needs ${v} more net income a month until month ${m}.`, goalOk: (g) => `<b>${g}</b>: reached without extra income.`,
    timingTitle: 'If the decision is delayed',
    timing: (d, nw, delta, short) => `Deciding <b>${d} months later</b>: net worth in 10 years ${nw} (${delta}); ${short}.`,
    shortFrom: (m) => `cash short from month ${m}`, never: 'cash never runs short', windowCut: ' Part of the change no longer fits before the 10-year horizon.',
    status: { threshold_found: 'threshold found', already_satisfied: 'already holds without any change', not_reached_within_bounds: 'not reached within the tested range', lever_has_no_effect: 'this assumption has no effect here', non_monotone: 'no single threshold: the effect goes up and down', already_broken: 'already broken without any change', evaluated: 'evaluated' },
    applied: 'Recomputed with your change. Reset it in the assumption editor below.',
  },
  es: {
    title: 'Qué tendría que pasar', condition: 'Si estos datos se cumplen, estas son las consecuencias con los supuestos indicados. Cada línea cambia una sola cosa y deja el resto igual.',
    stressTitle: '¿Cuánto imprevisto aguanta este plan?',
    broken: (m, low) => `<b>La liquidez ya se agota en este escenario</b>${m ? ` a partir del mes ${m}` : ''}${low ? ` (mínimo ${low})` : ''}, sin ningún imprevisto. Con estos supuestos el plan necesita dinero extra o un cambio.`,
    absorbs: (v) => `Aguanta un gasto imprevisto de hasta <b>${v}</b> hoy antes de quedarse sin liquidez o fallar un objetivo con fecha.`,
    unbreakable: (v) => `Ni siquiera un imprevisto de ${v} hoy lo rompería.`,
    leversTitle: 'Los supuestos que más mueven esta rama',
    lever: (l, base, u, lo, nwlo, hi, nwhi) => `<b>${l}</b> (ahora ${base}): con ${lo} el patrimonio a 10 años es ${nwlo}; con ${hi} es ${nwhi}.`,
    shortAt: 'falta liquidez', tryV: (v) => `Probar ${v}`,
    beTitle: 'Comparado con las otras opciones',
    ahead: (l, d) => `Termina <b>${d} por delante</b> de «${l}» a los 10 años.`, behind: (l, d) => `Termina <b>${d} por detrás</b> de «${l}» a los 10 años.`,
    crossover: (m) => ` Pasa por delante de forma definitiva desde el mes ${m}.`, aheadAll: ' Va por delante desde el principio.', neverAhead: ' Nunca se mantiene por delante.',
    sal: (l, v, u) => ` Ambas terminan igual si ${l} es <b>${v} ${u}</b>.`,
    goalTitle: 'Qué haría falta para cada objetivo',
    goalNeed: (g, v, m) => `<b>${g}</b>: necesita ${v} más de ingresos netos al mes hasta el mes ${m}.`, goalOk: (g) => `<b>${g}</b>: se alcanza sin ingresos extra.`,
    timingTitle: 'Si la decisión se retrasa',
    timing: (d, nw, delta, short) => `Decidir <b>${d} meses más tarde</b>: patrimonio a 10 años ${nw} (${delta}); ${short}.`,
    shortFrom: (m) => `falta liquidez desde el mes ${m}`, never: 'nunca falta liquidez', windowCut: ' Parte del cambio ya no cabe antes del horizonte de 10 años.',
    status: { threshold_found: 'umbral encontrado', already_satisfied: 'ya se cumple sin cambios', not_reached_within_bounds: 'no se alcanza en el rango probado', lever_has_no_effect: 'este supuesto no tiene efecto aquí', non_monotone: 'no hay un único umbral: el efecto sube y baja', already_broken: 'ya está roto sin cambios', evaluated: 'evaluado' },
    applied: 'Recalculado con tu cambio. Puedes deshacerlo en el editor de supuestos de abajo.',
  },
  fr: {
    title: 'Ce qui devrait être vrai', condition: 'Si ces données se vérifient, voici les conséquences selon les hypothèses indiquées. Chaque ligne change une seule chose et garde le reste.',
    stressTitle: 'Quel imprévu ce plan peut-il encaisser ?',
    broken: (m, low) => `<b>La trésorerie manque déjà dans ce scénario</b>${m ? ` dès le mois ${m}` : ''}${low ? ` (minimum ${low})` : ''}, sans aucun imprévu. Selon ces hypothèses, le plan a besoin d’argent en plus ou d’un changement.`,
    absorbs: (v) => `Il encaisse une dépense imprévue jusqu’à <b>${v}</b> aujourd’hui avant que la trésorerie manque ou qu’un objectif daté soit raté.`,
    unbreakable: (v) => `Même un imprévu de ${v} aujourd’hui ne le casserait pas.`,
    leversTitle: 'Les hypothèses qui font le plus bouger cette branche',
    lever: (l, base, u, lo, nwlo, hi, nwhi) => `<b>${l}</b> (actuellement ${base}) : à ${lo}, le patrimoine dans 10 ans est de ${nwlo} ; à ${hi}, de ${nwhi}.`,
    shortAt: 'trésorerie négative', tryV: (v) => `Essayer ${v}`,
    beTitle: 'Comparé aux autres options',
    ahead: (l, d) => `Finit <b>${d} devant</b> « ${l} » après 10 ans.`, behind: (l, d) => `Finit <b>${d} derrière</b> « ${l} » après 10 ans.`,
    crossover: (m) => ` Passe devant pour de bon dès le mois ${m}.`, aheadAll: ' Devant dès le début.', neverAhead: ' Ne reste jamais devant.',
    sal: (l, v, u) => ` Les deux finissent à égalité si ${l} vaut <b>${v} ${u}</b>.`,
    goalTitle: 'Ce qu’il faudrait pour chaque objectif',
    goalNeed: (g, v, m) => `<b>${g}</b> : il faut ${v} de revenu net en plus par mois jusqu’au mois ${m}.`, goalOk: (g) => `<b>${g}</b> : atteint sans revenu supplémentaire.`,
    timingTitle: 'Si la décision est retardée',
    timing: (d, nw, delta, short) => `Décider <b>${d} mois plus tard</b> : patrimoine dans 10 ans ${nw} (${delta}) ; ${short}.`,
    shortFrom: (m) => `trésorerie négative dès le mois ${m}`, never: 'la trésorerie ne manque jamais', windowCut: ' Une partie du changement ne tient plus avant l’horizon de 10 ans.',
    status: { threshold_found: 'seuil trouvé', already_satisfied: 'déjà vrai sans changement', not_reached_within_bounds: 'non atteint dans la plage testée', lever_has_no_effect: 'cette hypothèse n’a pas d’effet ici', non_monotone: 'pas de seuil unique : l’effet monte et descend', already_broken: 'déjà cassé sans changement', evaluated: 'évalué' },
    applied: 'Recalculé avec votre changement. Annulez-le dans l’éditeur d’hypothèses ci-dessous.',
  },
  de: {
    title: 'Was wahr sein müsste', condition: 'Wenn diese Eingaben zutreffen, folgen diese Konsequenzen unter den genannten Annahmen. Jede Zeile ändert nur eine Sache, der Rest bleibt gleich.',
    stressTitle: 'Wie viel Überraschung verträgt dieser Plan?',
    broken: (m, low) => `<b>In diesem Szenario fehlt bereits Liquidität</b>${m ? ` ab Monat ${m}` : ''}${low ? ` (Tiefstwert ${low})` : ''}, auch ohne unerwartete Kosten. Unter diesen Annahmen braucht der Plan zusätzliches Geld oder eine Änderung.`,
    absorbs: (v) => `Er verträgt heute unerwartete Kosten bis <b>${v}</b>, bevor die Liquidität fehlt oder ein datiertes Ziel verfehlt wird.`,
    unbreakable: (v) => `Selbst unerwartete Kosten von ${v} heute würden ihn nicht brechen.`,
    leversTitle: 'Die Annahmen, die diesen Ast am stärksten bewegen',
    lever: (l, base, u, lo, nwlo, hi, nwhi) => `<b>${l}</b> (jetzt ${base}): bei ${lo} liegt das Vermögen nach 10 Jahren bei ${nwlo}, bei ${hi} bei ${nwhi}.`,
    shortAt: 'Liquidität fehlt', tryV: (v) => `${v} ausprobieren`,
    beTitle: 'Im Vergleich zu den anderen Optionen',
    ahead: (l, d) => `Endet nach 10 Jahren <b>${d} vor</b> „${l}“.`, behind: (l, d) => `Endet nach 10 Jahren <b>${d} hinter</b> „${l}“.`,
    crossover: (m) => ` Ab Monat ${m} liegt er dauerhaft vorn.`, aheadAll: ' Von Anfang an vorn.', neverAhead: ' Bleibt nie dauerhaft vorn.',
    sal: (l, v, u) => ` Beide enden gleich, wenn ${l} <b>${v} ${u}</b> beträgt.`,
    goalTitle: 'Was es für jedes Ziel bräuchte',
    goalNeed: (g, v, m) => `<b>${g}</b>: braucht ${v} mehr Nettoeinkommen pro Monat bis Monat ${m}.`, goalOk: (g) => `<b>${g}</b>: wird ohne zusätzliches Einkommen erreicht.`,
    timingTitle: 'Wenn die Entscheidung später fällt',
    timing: (d, nw, delta, short) => `<b>${d} Monate später</b> entscheiden: Vermögen nach 10 Jahren ${nw} (${delta}); ${short}.`,
    shortFrom: (m) => `Liquidität fehlt ab Monat ${m}`, never: 'Liquidität fehlt nie', windowCut: ' Ein Teil der Änderung passt nicht mehr vor den 10-Jahres-Horizont.',
    status: { threshold_found: 'Schwelle gefunden', already_satisfied: 'gilt bereits ohne Änderung', not_reached_within_bounds: 'im getesteten Bereich nicht erreicht', lever_has_no_effect: 'diese Annahme hat hier keine Wirkung', non_monotone: 'keine eindeutige Schwelle: die Wirkung steigt und fällt', already_broken: 'bereits ohne Änderung gebrochen', evaluated: 'ausgewertet' },
    applied: 'Mit deiner Änderung neu berechnet. Im Annahmen-Editor unten kannst du sie zurücksetzen.',
  },
};

const signed = (d) => (Number.isFinite(d) ? (d >= 0 ? '+' : '−') + chf(Math.abs(d)).replace('CHF ', 'CHF ') : '–');

export function explorationSections(ex, { lang = 'en', metrics = {}, applied = false } = {}) {
  if (!ex || typeof ex !== 'object') return '';
  const L = EX_I18N[lang] || EX_I18N.en;
  const st = (s) => L.status[s] || String(s || '').replace(/_/g, ' ');
  const out = [];
  const leverLabel = (id) => (ex.levers || []).find((l) => l.assumption_id === id)?.label || id;

  // 1. robustness first: a broken plan must read as broken
  const rs = ex.reverse_stress;
  if (rs) {
    let line;
    if (rs.status === 'already_broken') {
      const m = month(rs.result?.first_negative_month ?? metrics.first_negative_month);
      const low = rs.result?.min_cash ?? metrics.min_cash;
      line = `<p class="ex-alert">${L.broken(m, Number.isFinite(low) && low < 0 ? chf(low) : '')}</p>`;
    } else if (rs.status === 'threshold_found' && rs.value != null) line = `<p>${L.absorbs(chf(rs.value))}</p>`;
    else if (rs.status === 'not_reached_within_bounds') line = `<p>${L.unbreakable(chf(rs.bounds?.[1]))}</p>`;
    else line = `<p>${esc(st(rs.status))}</p>`;
    out.push(`<div class="ex-block"><h4>${L.stressTitle}</h4>${line}</div>`);
  }

  // 2. levers, each with buttons that recompute the tree with that value
  if (Array.isArray(ex.levers) && ex.levers.length) {
    const items = ex.levers.slice(0, 5).map((l) => {
      const short = (b) => (b ? ` <span class="warn">(${L.shortAt})</span>` : '');
      const u = l.unit || '', bare = (v) => esc(fmtVal(v, /CHF/.test(u) ? '' : u));
      const text = L.lever(esc(l.label || l.assumption_id), esc(fmtVal(l.base_value, u)), '', bare(l.low_value), chf(l.final_net_worth_low) + short(l.cash_shortfall_low),
        bare(l.high_value), chf(l.final_net_worth_high) + short(l.cash_shortfall_high));
      const vals = [...new Set([l.low_value, l.high_value, ...Object.values(l.how_to_change?.assumptions || {})])].filter(Number.isFinite);
      const btns = vals.map((v) => `<button type="button" class="lever-btn" data-lever="${esc(l.assumption_id)}" data-value="${v}">${L.tryV(esc(fmtVal(v, /CHF/.test(u) ? '' : u)))}</button>`).join('');
      return `<li>${text}<span class="lever-btns">${btns}</span></li>`;
    }).join('');
    out.push(`<div class="ex-block"><h4>${L.leversTitle}</h4><ul class="levers">${items}</ul>${applied ? `<p class="note">${L.applied}</p>` : ''}</div>`);
  }

  // 3. break-even against each sibling
  if (Array.isArray(ex.break_even) && ex.break_even.length) {
    const items = ex.break_even.map((b) => {
      const d = b.delta_final_net_worth;
      let s = Number.isFinite(d) ? (d >= 0 ? L.ahead(esc(b.label), chf(Math.abs(d))) : L.behind(esc(b.label), chf(Math.abs(d)))) : esc(b.label);
      if (b.sustained_crossover_month === 0) s += L.aheadAll;
      else if (Number.isFinite(b.sustained_crossover_month)) s += L.crossover(month(b.sustained_crossover_month));
      else if (Number.isFinite(d) && d < 0) s += L.neverAhead;
      const t = b.salary_threshold;
      if (t) {
        if (t.status === 'threshold_found' && t.value != null) s += L.sal(esc(leverLabel(t.assumption_id)).toLowerCase(), num(t.value), esc(t.unit || ''));
        else s += ` <span class="status">(${esc(leverLabel(t.assumption_id))}: ${esc(st(t.status))})</span>`;
      }
      return `<li>${s}</li>`;
    }).join('');
    out.push(`<div class="ex-block"><h4>${L.beTitle}</h4><ul class="levers">${items}</ul></div>`);
  }

  // 4. goal seek
  if (Array.isArray(ex.goal_seek) && ex.goal_seek.length) {
    const items = ex.goal_seek.map((g) => {
      if (g.status === 'already_satisfied') return `<li>${L.goalOk(esc(g.goal))}</li>`;
      if (g.status === 'threshold_found' && g.value != null) return `<li>${L.goalNeed(esc(g.goal), chf(g.value), month(g.to_month) ?? '–')}</li>`;
      return `<li><b>${esc(g.goal)}</b>: ${esc(st(g.status))}</li>`;
    }).join('');
    out.push(`<div class="ex-block"><h4>${L.goalTitle}</h4><ul class="levers">${items}</ul></div>`);
  }

  // 5. timing
  if (Array.isArray(ex.timing) && ex.timing.length) {
    const items = ex.timing.map((x) => {
      if (x.final_net_worth == null) return `<li><b>+${x.delay_months}</b>: ${esc(st(x.status))}</li>`;
      const short = x.first_negative_month != null ? L.shortFrom(month(x.first_negative_month)) : L.never;
      return `<li>${L.timing(x.delay_months, chf(x.final_net_worth), signed(x.delta_final_net_worth), short)}${x.window_shortened ? `<span class="status">${L.windowCut}</span>` : ''}</li>`;
    }).join('');
    out.push(`<div class="ex-block"><h4>${L.timingTitle}</h4><ul class="levers">${items}</ul></div>`);
  }
  return out.length ? `<p class="note">${L.condition}</p>${out.join('')}` : '';
}

export const KNOWN_EXPLORATION = new Set(['basis', 'condition', 'levers', 'break_even', 'goal_seek', 'reverse_stress', 'timing']);
