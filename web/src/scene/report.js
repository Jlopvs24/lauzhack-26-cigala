import { explorationSections, KNOWN_EXPLORATION } from "./exploration.js";
import { planCheckHTML } from "./headline.js";
// The leaf report: exploration, not prediction. It leads with the deterministic scenario, then
// how this option differs from its siblings, then the levers ("what would have to be true").
// Monte Carlo is an optional "uncertainty lens", off by default. Unknown numeric result fields are
// listed at the end, so new engine fields show up without a UI change.

export const REPORT_I18N = {
  en: {
    exTitle: "What would have to be true", lensLoading: "Computing the uncertainty lens…", lensNa: "Not computed for this branch.",
    scenario: "This scenario", nw10: "Net worth in 10 years", lowCash: "Lowest cash", short: "Cash runs short",
    never: "never", month: "month", health: "Health score", chartTitle: "Cash and net worth, month by month",
    cash: "Cash", nw: "Net worth", vsTitle: "Compared with the other options here", option: "Option", thisOne: "this option",
    leversTitle: "What would have to be true", leverLine: (l, v, u, nw) => `If <b>${l}</b> were ${v}${u ? " " + u : ""}, net worth in 10 years would be ${nw}.`,
    leversNote: "Each line changes one assumption and keeps everything else as it is.",
    goalsTitle: "Goals in this scenario", reached: (m) => `reached in month ${m}`, notReached: "not reached",
    changesTitle: "What this choice changes", lens: "Uncertainty lens", lensNote: "Under these assumptions, the same plan replayed with random markets and job events. A spread of what could happen, not a forecast.",
    p50: "Median net worth in 10 years", range: "Range, 10th–90th percentile", paths: "Futures where cash runs out", goalP: "Chance of reaching",
    checks: (p, n) => `${p} of ${n} accounting checks passed`, more: "All other results",
  },
  es: {
    exTitle: "Qué tendría que pasar", lensLoading: "Calculando la lente de incertidumbre…", lensNa: "No calculado para esta rama.",
    scenario: "Este escenario", nw10: "Patrimonio en 10 años", lowCash: "Liquidez mínima", short: "Falta liquidez",
    never: "nunca", month: "mes", health: "Salud financiera", chartTitle: "Liquidez y patrimonio, mes a mes",
    cash: "Liquidez", nw: "Patrimonio", vsTitle: "Comparado con las otras opciones", option: "Opción", thisOne: "esta opción",
    leversTitle: "Qué tendría que pasar", leverLine: (l, v, u, nw) => `Si <b>${l}</b> fuera ${v}${u ? " " + u : ""}, el patrimonio a 10 años sería ${nw}.`,
    leversNote: "Cada línea cambia un solo supuesto y deja el resto igual.",
    goalsTitle: "Objetivos en este escenario", reached: (m) => `se alcanza en el mes ${m}`, notReached: "no se alcanza",
    changesTitle: "Qué cambia esta decisión", lens: "Lente de incertidumbre", lensNote: "Con estos supuestos, el mismo plan repetido con mercados y eventos laborales aleatorios. Un abanico de lo que podría pasar, no una predicción.",
    p50: "Patrimonio mediano a 10 años", range: "Rango, percentil 10–90", paths: "Futuros sin liquidez", goalP: "Probabilidad de lograr",
    checks: (p, n) => `${p} de ${n} controles contables superados`, more: "Resto de resultados",
  },
  fr: {
    exTitle: "Ce qui devrait être vrai", lensLoading: "Calcul de la lentille d’incertitude…", lensNa: "Non calculé pour cette branche.",
    scenario: "Ce scénario", nw10: "Patrimoine dans 10 ans", lowCash: "Trésorerie minimale", short: "Trésorerie négative",
    never: "jamais", month: "mois", health: "Santé financière", chartTitle: "Trésorerie et patrimoine, mois par mois",
    cash: "Trésorerie", nw: "Patrimoine", vsTitle: "Comparé aux autres options", option: "Option", thisOne: "cette option",
    leversTitle: "Ce qui devrait être vrai", leverLine: (l, v, u, nw) => `Si <b>${l}</b> valait ${v}${u ? " " + u : ""}, le patrimoine dans 10 ans serait de ${nw}.`,
    leversNote: "Chaque ligne change une seule hypothèse et garde le reste.",
    goalsTitle: "Objectifs dans ce scénario", reached: (m) => `atteint au mois ${m}`, notReached: "non atteint",
    changesTitle: "Ce que ce choix change", lens: "Lentille d'incertitude", lensNote: "Selon ces hypothèses, le même plan rejoué avec des marchés et des événements professionnels aléatoires. Un éventail de ce qui pourrait arriver, pas une prévision.",
    p50: "Patrimoine médian dans 10 ans", range: "Fourchette, 10e–90e centile", paths: "Futurs à court de trésorerie", goalP: "Chance d'atteindre",
    checks: (p, n) => `${p} contrôles comptables sur ${n} réussis`, more: "Tous les autres résultats",
  },
  de: {
    exTitle: "Was wahr sein müsste", lensLoading: "Unsicherheits-Linse wird berechnet…", lensNa: "Für diesen Ast nicht berechnet.",
    scenario: "Dieses Szenario", nw10: "Vermögen in 10 Jahren", lowCash: "Tiefste Liquidität", short: "Liquidität fehlt",
    never: "nie", month: "Monat", health: "Finanzgesundheit", chartTitle: "Liquidität und Vermögen, Monat für Monat",
    cash: "Liquidität", nw: "Vermögen", vsTitle: "Im Vergleich zu den anderen Optionen", option: "Option", thisOne: "diese Option",
    leversTitle: "Was wahr sein müsste", leverLine: (l, v, u, nw) => `Wenn <b>${l}</b> ${v}${u ? " " + u : ""} wäre, läge das Vermögen nach 10 Jahren bei ${nw}.`,
    leversNote: "Jede Zeile ändert eine einzige Annahme, alles andere bleibt gleich.",
    goalsTitle: "Ziele in diesem Szenario", reached: (m) => `erreicht in Monat ${m}`, notReached: "nicht erreicht",
    changesTitle: "Was diese Entscheidung ändert", lens: "Unsicherheits-Linse", lensNote: "Unter diesen Annahmen, derselbe Plan mit zufälligen Märkten und Jobereignissen durchgespielt. Eine Bandbreite dessen, was passieren könnte, keine Prognose.",
    p50: "Medianvermögen in 10 Jahren", range: "Spanne, 10.–90. Perzentil", paths: "Zukünfte ohne Liquidität", goalP: "Chance zu erreichen",
    checks: (p, n) => `${p} von ${n} Buchhaltungsprüfungen bestanden`, more: "Alle weiteren Ergebnisse",
  },
};

export const fmtCHF = (n) => (n == null || Number.isNaN(n) ? "–" : (n < 0 ? "−" : "") + "CHF " + Math.abs(Math.round(n)).toLocaleString("en-US").replace(/,/g, "’"));
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const last = (a) => (Array.isArray(a) && a.length ? a[a.length - 1] : null);

// Deterministic cash + net worth lines; with the lens on, the Monte Carlo band behind net worth.
export function scenarioChart(r, { lens = false, L }) {
  const det = r.deterministic || {};
  const cash = det.cash || [], nw = det.net_worth || [];
  const b = r.bands?.net_worth;
  const band = lens && b?.p10?.length && b?.p90?.length ? b : null; // empty arrays when not computed
  const n = Math.max(cash.length, nw.length);
  if (n < 2) return "";
  const all = [...cash, ...nw, 0, ...(band ? [...band.p10, ...band.p90] : [])].filter(Number.isFinite);
  const lo = Math.min(...all), hi = Math.max(...all);
  const X = (i) => (i / (n - 1)) * 360, Y = (v) => 128 - ((v - lo) / (hi - lo || 1)) * 116;
  const pts = (a) => a.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  const neg = cash.findIndex((v) => v < 0);
  const area = band ? `<polygon class="area" points="${pts(band.p90)} ${band.p10.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).reverse().join(" ")}"/>` : "";
  const years = [0, 2, 4, 6, 8, 10].map((y) => `<text x="${X(Math.min(n - 1, y * 12))}" y="146" class="axis">${y === 0 ? "0" : y + "y"}</text>`).join("");
  return `<svg class="chart" viewBox="-4 0 372 150" role="img" aria-label="${esc(L.chartTitle)}">
    <line x1="0" x2="360" y1="${Y(0)}" y2="${Y(0)}" class="zero"/>
    ${area}
    <polyline points="${pts(nw)}" class="nw" fill="none"/>
    <polyline points="${pts(cash)}" class="cash" fill="none"/>
    ${neg >= 0 ? `<circle cx="${X(neg)}" cy="${Y(cash[neg])}" r="3.5" class="negdot"/>` : ""}
    ${years}
  </svg>
  <div class="legend"><span class="k nw"></span>${esc(L.nw)}<span class="k cash"></span>${esc(L.cash)}</div>`;
}

export function renderReport({ data, lang, ui, tr, lens, lensPending = false, applied = false }) {
  const L = REPORT_I18N[lang] || REPORT_I18N.en;
  const cur = data.nodes.find((n) => n.node_id === data.current);
  const r = cur.result || {}, m = r.metrics || {}, h = r.health || {};
  const c = tr(cur);
  const shortM = m.first_negative_month != null ? m.first_negative_month + 1 : null;
  const detNW = r.deterministic?.final_net_worth ?? m.final_net_worth ?? last(r.deterministic?.net_worth);

  // siblings (and the current node) at this level, for the comparison table
  const peers = data.nodes.filter((n) => n.parent_id === cur.parent_id && n.result && (n.status === "sibling" || n.node_id === cur.node_id));
  const vs = cur.node_id !== "0" && peers.length > 1 ? `
    <h3>${L.vsTitle}</h3>
    <table class="vs"><thead><tr><th>${L.option}</th><th>${L.nw10}</th><th>${L.short}</th></tr></thead><tbody>
    ${peers.map((p) => {
      const pm = p.result.metrics, me = p.node_id === cur.node_id;
      const d = me ? "" : `<span class="delta ${pm.final_net_worth - m.final_net_worth >= 0 ? "up" : "down"}">${pm.final_net_worth - m.final_net_worth >= 0 ? "+" : "−"}${fmtCHF(Math.abs(pm.final_net_worth - m.final_net_worth)).replace("CHF ", "")}</span>`;
      return `<tr class="${me ? "me" : ""}"><td>${esc(tr(p).label)}${me ? ` <i>(${L.thisOne})</i>` : ""}</td><td>${fmtCHF(pm.final_net_worth)} ${d}</td><td class="${pm.first_negative_month != null ? "warn" : ""}">${pm.first_negative_month != null ? L.month + " " + (pm.first_negative_month + 1) : L.never}</td></tr>`;
    }).join("")}</tbody></table>` : "";

  // "what would have to be true": the engine's exploration block (#21) when present, else sensitivity
  let levers = "";
  const ex = r.exploration || cur.exploration;
  const unknown = ex && typeof ex === "object" ? Object.fromEntries(Object.entries(ex).filter(([k]) => !KNOWN_EXPLORATION.has(k))) : null;
  const exHTML = ex ? explorationSections(ex, { lang, metrics: m, applied }) + explorationHTML(unknown) : "";
  if (exHTML) {
    levers = exHTML;
  } else if (Array.isArray(r.sensitivity) && r.sensitivity.length) {
    levers = r.sensitivity.slice(0, 3).flatMap((s) => [
      `<li>${L.leverLine(esc(s.label), s.low_value, esc(s.unit), fmtCHF(s.final_net_worth_low))}</li>`,
      `<li>${L.leverLine(esc(s.label), s.high_value, esc(s.unit), fmtCHF(s.final_net_worth_high))}</li>`,
    ]).join("");
  }
  const goals = (r.goals || []).map((g) => `<dt>${esc(g.name)}</dt><dd>${g.met_deterministic ? L.reached((g.first_reached_month_deterministic ?? 0) + 1) : `<span class="warn">${L.notReached}</span>`}</dd>`).join("");

  const stochastic = m.final_net_worth_p50 != null;
  const lensHTML = lens && !stochastic ? `<p class="note lens-body">${lensPending ? L.lensLoading : L.lensNa}</p>` : lens ? `
    <div class="lens-body">
      <p class="note">${L.lensNote}</p>
      <dl>
        <dt>${L.p50}</dt><dd>${fmtCHF(m.final_net_worth_p50)}</dd>
        <dt>${L.range}</dt><dd>${fmtCHF(m.final_net_worth_p10)} – ${fmtCHF(m.final_net_worth_p90)}</dd>
        <dt>${L.paths}</dt><dd>${m.shortfall_probability != null ? Math.round(m.shortfall_probability * 100) + "%" : "–"}</dd>
        ${Object.entries(m.goal_probability || {}).filter(([, v]) => v != null).map(([k, v]) => `<dt>${L.goalP}: ${esc(k)}</dt><dd>${Math.round(v * 100)}%</dd>`).join("")}
      </dl>
    </div>` : "";

  const shown = new Set(["final_net_worth", "min_cash", "first_negative_month", "final_net_worth_p10", "final_net_worth_p50", "final_net_worth_p90", "shortfall_probability", "goal_probability"]);
  const more = Object.entries(m).filter(([k, v]) => !shown.has(k) && typeof v === "number")
    .map(([k, v]) => `<dt>${esc(k.replace(/_/g, " "))}</dt><dd>${/month/.test(k) ? v : Math.abs(v) > 50 ? fmtCHF(v) : Math.round(v * 1000) / 1000}</dd>`).join("");
  const passed = (r.checks || []).filter((x) => x.passed).length;

  return `
    <div class="kicker">${cur.node_id === "0" ? ui.today : ui.branch + " " + esc(cur.node_id)}</div>
    <h2>${esc(c.label)}</h2>
    <p class="desc">${esc(c.desc)}</p>
    ${planCheckHTML(r, lang, esc)}
    <h3>${L.scenario}</h3>
    <div class="hero-num"><b>${fmtCHF(detNW)}</b><span>${L.nw10}</span></div>
    <dl class="facts">
      <dt>${L.lowCash}</dt><dd class="${m.min_cash < 0 ? "warn" : ""}">${fmtCHF(m.min_cash)}</dd>
      <dt>${L.short}</dt><dd class="${shortM ? "warn" : ""}">${shortM ? L.month + " " + shortM : L.never}</dd>
    </dl>
    ${levers ? (exHTML ? `<h3>${L.exTitle}</h3>${levers}` : `<h3>${L.leversTitle}</h3><ul class="levers">${levers}</ul><p class="note">${L.leversNote}</p>`) : ""}
    <h3>${L.chartTitle}</h3>
    ${scenarioChart(r, { lens, L })}
    ${vs}
    ${goals ? `<h3>${L.goalsTitle}</h3><dl>${goals}</dl>` : ""}
    ${lang === "en" && cur.changes?.length ? `<h3>${L.changesTitle}</h3><ul>${cur.changes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    <div class="lens"><label class="switch"><input type="checkbox" id="lensToggle" ${lens ? "checked" : ""}><span class="track"></span>${L.lens}</label></div>
    ${lensHTML}
    ${more ? `<details class="more"><summary>${L.more}</summary><dl>${more}</dl></details>` : ""}
    <p class="note checks">${L.checks(passed, (r.checks || []).length)}${r.engine_version ? " · " + esc(r.engine_version) : ""}</p>`;
}

// Generic renderer for the engine's `exploration` block. Known shapes get a sentence; anything else
// is shown as its own text/summary field or as compact key: value pairs, so new fields never break it.
const pick = (x) => (typeof x === "string" ? x : x && (x.text || x.summary || x.explanation || x.description || x.label));
const human = (k) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
function val(k, v) {
  if (typeof v !== "number") return esc(typeof v === "object" ? JSON.stringify(v) : v);
  if (/month/.test(k)) return String(Math.round(v));
  if (/prob|share|ratio|rate/.test(k) && Math.abs(v) <= 1) return Math.round(v * 1000) / 10 + "%";
  return Math.abs(v) >= 50 ? fmtCHF(v) : String(Math.round(v * 100) / 100);
}
function itemHTML(x) {
  const t = pick(x);
  if (t) return `<li>${esc(t)}</li>`;
  if (x && typeof x === "object") {
    const kv = Object.entries(x).filter(([, v]) => v != null && typeof v !== "object").slice(0, 5).map(([k, v]) => `${esc(human(k))}: <b>${val(k, v)}</b>`).join(" · ");
    return kv ? `<li>${kv}</li>` : "";
  }
  return "";
}
export function explorationHTML(ex) {
  if (!ex || typeof ex !== "object") return "";
  return Object.entries(ex).map(([k, v]) => {
    if (v == null) return "";
    const items = Array.isArray(v) ? v.map(itemHTML).join("") : pick(v) ? `<li>${esc(pick(v))}</li>` : typeof v === "object" ? itemHTML(v) : `<li>${val(k, v)}</li>`;
    return items ? `<div class="ex-block"><h4>${esc(human(k))}</h4><ul class="levers">${items}</ul></div>` : "";
  }).join("");
}
