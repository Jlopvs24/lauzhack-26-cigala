import React, { useEffect, useState } from 'react';
import { fetchPathReport } from './pathReport.js';
import { explorationSections } from '../scene/exploration.js';
import { planCheckHTML, cardHeadline, H_I18N } from '../scene/headline.js';

const chf = (n) => (Number.isFinite(n) ? (n < 0 ? '−' : '') + 'CHF ' + Math.abs(Math.round(n)).toLocaleString('en-US').replace(/,/g, '’') : '–');
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

const R = {
  en: { title: 'Your path report', print: 'Save as PDF', close: 'Close', loading: 'Putting the report together from the engine…', source: (s) => (s === 'report' ? 'Built by the report service from the engine.' : 'Built in the browser from the engine (report service not available yet).'),
    s: ['Summary', 'Question and scope', 'Starting point', 'Each decision on this path', 'Compared with the alternatives at every step', 'What would have to be true, step by step', 'Stress scenarios', 'Limits, targets and breaches', 'What the numbers leave out', 'Uncertainty lens (optional)', 'Validation and reproducibility', 'Limitations and responsible design'],
    summary: (who, steps, nw, low, gap, pc, h, o) => `If ${who} ${steps}, then under these assumptions: net worth after 10 years ${nw} in today's prices, lowest cash ${low}${gap ? `, with a funding gap from month ${gap}` : ''}. Plan check: ${pc}.${o ? ` It holds in ${h} of ${o} stress scenarios.` : ''} This is an exploration, not a forecast and not advice.`,
    then: ', then ', horizon: 'Horizon', months: 'months', currency: 'Currency', where: 'Jurisdiction', asOf: 'As of', values: 'Values', path: 'Path', field: 'Field', value: 'Value', origin: 'Origin',
    changes: 'What it changes', introduced: 'Assumptions it introduces', vsBefore: 'Compared with before this choice', option: 'Option', nwReal: 'Net worth in 10 years (today’s prices)', low: 'Lowest cash', goals: 'Goals met', debt: 'Debt in 10 years', check: 'Plan check', chosen: 'chosen',
    weather: { none: 'As planned', recession: 'Recession', inflation: 'High inflation', market_crash: 'Market crash', job_loss: 'Job loss' }, holds: 'Holds', breaks: 'Breaks', shortFrom: 'Cash short from', surplus: 'Monthly change in cash', gapLen: (n) => `Cash is negative in ${n} of the months.`,
    qual: 'Qualitative, not modelled by the engine:', lensOff: 'Off. Turn it on to replay this path with random markets, inflation and job events.', lensBtn: 'Turn on the uncertainty lens', lensNote: 'Shares of simulated paths under these assumptions, not real-world probabilities.',
    checks: 'Accounting checks', reproduce: 'Reproduce this report', responsible: 'Every number on this page comes from the tested engine; the language model only words numbers it is given and cannot create new ones. Lumi explains options and never recommends one. Nothing here is a forecast or financial advice.',
    q: { education: 'education and a degree, with later full earnings', location: 'where she lives: distance from family and friends, a new city or country', time: 'free time and flexibility versus income', mobility: 'mobility and independence a car gives', space: 'privacy and space versus a lower rent', risk: 'comfort with market ups and downs' } },
  es: { title: 'Tu informe del camino', print: 'Guardar como PDF', close: 'Cerrar', loading: 'Preparando el informe con el motor…', source: (s) => (s === 'report' ? 'Generado por el servicio de informes a partir del motor.' : 'Generado en el navegador a partir del motor (el servicio de informes aún no está disponible).'),
    s: ['Resumen', 'Pregunta y alcance', 'Punto de partida', 'Cada decisión del camino', 'Comparado con las alternativas en cada paso', 'Qué tendría que pasar, paso a paso', 'Escenarios de estrés', 'Límites, objetivos e incumplimientos', 'Lo que los números no recogen', 'Lente de incertidumbre (opcional)', 'Validación y reproducibilidad', 'Limitaciones y diseño responsable'],
    summary: (who, steps, nw, low, gap, pc, h, o) => `Si ${who} decide ${steps}, con estos supuestos: patrimonio a 10 años ${nw} a precios de hoy, liquidez mínima ${low}${gap ? `, con falta de financiación desde el mes ${gap}` : ''}. Revisión del plan: ${pc}.${o ? ` Se sostiene en ${h} de ${o} escenarios de estrés.` : ''} Es una exploración, no una predicción ni un consejo.`,
    then: ', después ', horizon: 'Horizonte', months: 'meses', currency: 'Moneda', where: 'Jurisdicción', asOf: 'Fecha', values: 'Valores', path: 'Camino', field: 'Dato', value: 'Valor', origin: 'Origen',
    changes: 'Qué cambia', introduced: 'Supuestos que introduce', vsBefore: 'Comparado con antes de esta decisión', option: 'Opción', nwReal: 'Patrimonio a 10 años (precios de hoy)', low: 'Liquidez mínima', goals: 'Objetivos cumplidos', debt: 'Deuda a 10 años', check: 'Revisión del plan', chosen: 'elegida',
    weather: { none: 'Según lo previsto', recession: 'Recesión', inflation: 'Inflación alta', market_crash: 'Caída de mercados', job_loss: 'Pérdida de empleo' }, holds: 'Se sostiene', breaks: 'Se rompe', shortFrom: 'Falta liquidez desde', surplus: 'Variación mensual de liquidez', gapLen: (n) => `La liquidez es negativa en ${n} de los meses.`,
    qual: 'Cualitativo, el motor no lo modela:', lensOff: 'Desactivada. Actívala para repetir este camino con mercados, inflación y eventos laborales aleatorios.', lensBtn: 'Activar la lente de incertidumbre', lensNote: 'Proporciones de trayectorias simuladas con estos supuestos, no probabilidades reales.',
    checks: 'Controles contables', reproduce: 'Reproducir este informe', responsible: 'Cada número de esta página sale del motor verificado; el modelo de lenguaje solo redacta números que recibe y no puede crear otros. Lumi explica opciones y nunca recomienda una. Nada de esto es una predicción ni un consejo financiero.',
    q: { education: 'formación y un título, con ingresos completos más tarde', location: 'dónde vive: lejos de familia y amigos, una ciudad o país nuevo', time: 'tiempo libre y flexibilidad frente a ingresos', mobility: 'la movilidad e independencia de un coche', space: 'intimidad y espacio frente a un alquiler más bajo', risk: 'tranquilidad ante los vaivenes del mercado' } },
  fr: { title: 'Votre rapport de parcours', print: 'Enregistrer en PDF', close: 'Fermer', loading: 'Préparation du rapport avec le moteur…', source: (s) => (s === 'report' ? 'Produit par le service de rapports à partir du moteur.' : 'Produit dans le navigateur à partir du moteur (service de rapports pas encore disponible).'),
    s: ['Résumé', 'Question et périmètre', 'Point de départ', 'Chaque décision du parcours', 'Comparé aux alternatives à chaque étape', 'Ce qui devrait être vrai, étape par étape', 'Scénarios de stress', 'Limites, objectifs et dépassements', 'Ce que les chiffres ne disent pas', 'Lentille d’incertitude (facultative)', 'Validation et reproductibilité', 'Limites et conception responsable'],
    summary: (who, steps, nw, low, gap, pc, h, o) => `Si ${who} choisit ${steps}, alors selon ces hypothèses : patrimoine dans 10 ans ${nw} aux prix d’aujourd’hui, trésorerie minimale ${low}${gap ? `, avec un besoin de financement dès le mois ${gap}` : ''}. Contrôle du plan : ${pc}.${o ? ` Il tient dans ${h} scénarios de stress sur ${o}.` : ''} C’est une exploration, pas une prévision ni un conseil.`,
    then: ', puis ', horizon: 'Horizon', months: 'mois', currency: 'Monnaie', where: 'Juridiction', asOf: 'Date', values: 'Valeurs', path: 'Parcours', field: 'Donnée', value: 'Valeur', origin: 'Origine',
    changes: 'Ce que cela change', introduced: 'Hypothèses introduites', vsBefore: 'Par rapport à avant ce choix', option: 'Option', nwReal: 'Patrimoine dans 10 ans (prix d’aujourd’hui)', low: 'Trésorerie minimale', goals: 'Objectifs atteints', debt: 'Dette dans 10 ans', check: 'Contrôle du plan', chosen: 'choisie',
    weather: { none: 'Comme prévu', recession: 'Récession', inflation: 'Forte inflation', market_crash: 'Krach boursier', job_loss: 'Perte d’emploi' }, holds: 'Tient', breaks: 'Casse', shortFrom: 'Trésorerie négative dès', surplus: 'Variation mensuelle de la trésorerie', gapLen: (n) => `La trésorerie est négative pendant ${n} mois.`,
    qual: 'Qualitatif, non modélisé par le moteur :', lensOff: 'Désactivée. Activez-la pour rejouer ce parcours avec des marchés, une inflation et des événements professionnels aléatoires.', lensBtn: 'Activer la lentille d’incertitude', lensNote: 'Parts de trajectoires simulées selon ces hypothèses, pas des probabilités réelles.',
    checks: 'Contrôles comptables', reproduce: 'Reproduire ce rapport', responsible: 'Chaque chiffre de cette page vient du moteur testé ; le modèle de langage ne fait que formuler les chiffres reçus et ne peut pas en créer. Lumi explique les options et n’en recommande jamais une. Rien ici n’est une prévision ni un conseil financier.',
    q: { education: 'la formation et un diplôme, avec un plein salaire plus tard', location: 'le lieu de vie : loin de la famille et des amis, une nouvelle ville ou un nouveau pays', time: 'le temps libre et la flexibilité face au revenu', mobility: 'la mobilité et l’indépendance d’une voiture', space: 'l’intimité et l’espace face à un loyer plus bas', risk: 'la sérénité face aux hauts et bas des marchés' } },
  de: { title: 'Dein Pfad-Bericht', print: 'Als PDF speichern', close: 'Schließen', loading: 'Der Bericht wird aus der Engine zusammengestellt…', source: (s) => (s === 'report' ? 'Vom Berichtsdienst aus der Engine erstellt.' : 'Im Browser aus der Engine erstellt (Berichtsdienst noch nicht verfügbar).'),
    s: ['Zusammenfassung', 'Frage und Rahmen', 'Ausgangslage', 'Jede Entscheidung auf diesem Pfad', 'Im Vergleich zu den Alternativen bei jedem Schritt', 'Was wahr sein müsste, Schritt für Schritt', 'Stressszenarien', 'Grenzen, Ziele und Verletzungen', 'Was die Zahlen nicht erfassen', 'Unsicherheits-Linse (optional)', 'Validierung und Reproduzierbarkeit', 'Grenzen und verantwortungsvolles Design'],
    summary: (who, steps, nw, low, gap, pc, h, o) => `Wenn ${who} ${steps} wählt, dann unter diesen Annahmen: Vermögen nach 10 Jahren ${nw} zu heutigen Preisen, tiefste Liquidität ${low}${gap ? `, mit einer Finanzierungslücke ab Monat ${gap}` : ''}. Plan-Check: ${pc}.${o ? ` Er hält in ${h} von ${o} Stressszenarien.` : ''} Das ist eine Erkundung, keine Prognose und keine Beratung.`,
    then: ', dann ', horizon: 'Horizont', months: 'Monate', currency: 'Währung', where: 'Rechtsraum', asOf: 'Stand', values: 'Werte', path: 'Pfad', field: 'Angabe', value: 'Wert', origin: 'Herkunft',
    changes: 'Was sich ändert', introduced: 'Eingeführte Annahmen', vsBefore: 'Im Vergleich zu vor dieser Entscheidung', option: 'Option', nwReal: 'Vermögen nach 10 Jahren (heutige Preise)', low: 'Tiefste Liquidität', goals: 'Erreichte Ziele', debt: 'Schulden nach 10 Jahren', check: 'Plan-Check', chosen: 'gewählt',
    weather: { none: 'Wie geplant', recession: 'Rezession', inflation: 'Hohe Inflation', market_crash: 'Börsencrash', job_loss: 'Jobverlust' }, holds: 'Hält', breaks: 'Bricht', shortFrom: 'Liquidität fehlt ab', surplus: 'Monatliche Veränderung der Liquidität', gapLen: (n) => `Die Liquidität ist in ${n} Monaten negativ.`,
    qual: 'Qualitativ, nicht von der Engine modelliert:', lensOff: 'Aus. Einschalten, um diesen Pfad mit zufälligen Märkten, Inflation und Jobereignissen durchzuspielen.', lensBtn: 'Unsicherheits-Linse einschalten', lensNote: 'Anteile simulierter Pfade unter diesen Annahmen, keine realen Wahrscheinlichkeiten.',
    checks: 'Buchhaltungsprüfungen', reproduce: 'Diesen Bericht reproduzieren', responsible: 'Jede Zahl auf dieser Seite stammt aus der geprüften Engine; das Sprachmodell formuliert nur übergebene Zahlen und kann keine neuen erzeugen. Lumi erklärt Optionen und empfiehlt nie eine. Nichts hier ist eine Prognose oder Finanzberatung.',
    q: { education: 'Ausbildung und ein Abschluss, mit vollem Einkommen erst später', location: 'der Wohnort: weg von Familie und Freunden, eine neue Stadt oder ein neues Land', time: 'Freizeit und Flexibilität gegenüber Einkommen', mobility: 'Mobilität und Unabhängigkeit durch ein Auto', space: 'Privatsphäre und Platz gegenüber tieferer Miete', risk: 'Gelassenheit bei Marktschwankungen' } },
};
const QUAL = [[/master|stud|scholar|graduat|internship|tuition|drop out/i, 'education'], [/abroad|zurich|lausanne|come back|move/i, 'location'],
  [/80%|60%|part-time|sabbatical|pause|side (job|project)|raise|promotion/i, 'time'], [/car/i, 'mobility'], [/share|shared|flat alone/i, 'space'], [/equit|invest|stay the course/i, 'risk']];

function Spark({ values }) {
  if (!values?.length) return null;
  const lo = Math.min(0, ...values), hi = Math.max(0, ...values), n = values.length;
  const X = (i) => (i / (n - 1)) * 600, Y = (v) => 90 - ((v - lo) / (hi - lo || 1)) * 80;
  return <svg className="pr-spark" viewBox="0 0 600 100" preserveAspectRatio="none" aria-hidden="true">
    <line x1="0" x2="600" y1={Y(0)} y2={Y(0)} className="zero" />
    {values.map((v, i) => <rect key={i} x={X(i) - 2} width="4" y={Math.min(Y(v), Y(0))} height={Math.abs(Y(v) - Y(0)) || 0.5} className={v < 0 ? 'neg' : 'pos'} />)}
  </svg>;
}

export default function PathReport({ lang, tr, profile, path, assumptions, onClose }) {
  const L = R[lang] || R.en, H = H_I18N[lang] || H_I18N.en;
  const [data, setData] = useState(null), [error, setError] = useState(''), [lens, setLens] = useState(false);
  useEffect(() => {
    let live = true; setData(null); setError('');
    fetchPathReport({ profile, path, assumptions, uncertainty: lens }).then((d) => live && setData(d)).catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [JSON.stringify(path), JSON.stringify(assumptions), lens, profile]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const k = (e) => e.key === 'Escape' && onClose(); addEventListener('keydown', k); return () => removeEventListener('keydown', k); }, [onClose]);

  const name = (n) => tr({ label: n.label, description: n.description }).label;
  const head = <header className="pr-top"><span className="pr-brand">cigala</span>
    <div className="pr-actions"><button className="ghost" onClick={() => print()}>{L.print}</button><button className="ghost" onClick={onClose}>{L.close}</button></div></header>;
  if (!data) return <div className="path-report" role="dialog" aria-modal="true" aria-label={L.title}>{head}<main className="pr-body"><p className="pr-loading">{error || L.loading}</p></main></div>;

  const leaf = data.steps.at(-1), leafRes = leaf?.result;
  const s = data.stress?.[0]?.summary || {};
  const wr = data.leaf.weather_resilience;
  const pcLabel = (H.level[data.leaf.plan_check?.level] || data.leaf.plan_check?.label || '').toLowerCase();
  const stepsText = data.steps.map((x) => name(x).replace(/^./, (c) => c.toLowerCase())).join(L.then);
  const sec = (i, body, cls = '') => <section className={`pr-sec ${cls}`} key={i}><h2><span>{String(i + 1).padStart(2, '0')}</span>{L.s[i]}</h2>{body}</section>;
  const row = (label, sm, me) => <tr className={me ? 'me' : ''} key={label}><th scope="row">{label}{me && <small> · {L.chosen}</small>}</th>
    <td>{chf(sm.final_net_worth_real)}</td><td className={sm.min_cash < 0 ? 'neg' : ''}>{chf(sm.min_cash)}</td>
    <td>{sm.goals_total != null ? `${sm.goals_met}/${sm.goals_total}` : '–'}</td><td>{chf(sm.final_debt)}</td><td>{H.level[sm.plan_check] || '–'}</td></tr>;
  const negMonths = (data.leaf.monthly_surplus || []).length ? (leafRes?.deterministic?.cash || []).filter((v) => v < 0).length : 0;

  return <div className="path-report" role="dialog" aria-modal="true" aria-label={L.title}>{head}
    <main className="pr-body">
      <p className="pr-kicker">{L.title}</p>
      <h1>{data.steps.map((x) => name(x)).join(' → ') || name(data.baseline)}</h1>
      <p className="pr-source">{L.source(data.source)}</p>

      {sec(0, <p className="pr-lead">{L.summary(profile?.display_name || 'Alexia', stepsText, chf(s.final_net_worth_real), chf(s.min_cash),
        s.first_negative_month != null ? s.first_negative_month + 1 : null, pcLabel, wr?.holds_in ?? 0, wr?.of ?? 0)}</p>)}

      {sec(1, <dl className="pr-facts">
        <dt>{L.path}</dt><dd>{[data.baseline, ...data.steps].map((x) => name(x)).join(' → ')}</dd>
        <dt>{L.horizon}</dt><dd>{data.question.horizon_months} {L.months}</dd><dt>{L.currency}</dt><dd>{data.question.currency}</dd>
        <dt>{L.where}</dt><dd>{data.question.jurisdiction}</dd><dt>{L.asOf}</dt><dd>{data.question.as_of}</dd><dt>{L.values}</dt><dd>{data.question.values}</dd></dl>)}

      {sec(2, data.starting_state?.length ? <table className="pr-table"><thead><tr><th>{L.field}</th><th>{L.value}</th><th>{L.origin}</th></tr></thead>
        <tbody>{data.starting_state.map((f) => <tr key={f.field}><th scope="row">{f.field.replace(/_/g, ' ')}</th><td>{typeof f.value === 'number' ? (/age|month/.test(f.field) ? f.value : chf(f.value)) : String(f.value ?? '–')}</td>
          <td><span className={`chip ${f.label}`}>{f.label}</span> <small>{f.source}</small></td></tr>)}</tbody></table> : <p>–</p>)}

      {sec(3, data.steps.map((st) => { const h = cardHeadline(st.result, lang); return <article className="pr-step" key={st.node_id}>
        <h3>{name(st)}</h3><p>{tr(st).desc}</p>
        {h && <p className="pr-slots">{h.a && <span className={`slot-a ${h.a.kind}`}>{h.a.text}</span>}{h.b && <span>{h.b.text}{h.b.vs && <i> · {h.b.vs}</i>}</span>}</p>}
        {!!st.changes?.length && <><h4>{L.changes}</h4><ul>{st.changes.map((c, i) => <li key={i}>{c}</li>)}</ul></>}
        {!!st.assumptions_introduced?.length && <><h4>{L.introduced}</h4><ul>{st.assumptions_introduced.map((a) => <li key={a.id}>{a.label}: <b>{a.value} {a.unit}</b>
          <small> · {a.kind || 'assumption'} · {a.source || '–'}{a.verified === false ? ' · not verified' : ''}</small></li>)}</ul></>}
        <h4>{L.vsBefore}</h4><p className="pr-delta">{L.nwReal}: {st.delta_vs_parent?.final_net_worth_real != null ? (st.delta_vs_parent.final_net_worth_real >= 0 ? '+' : '') + chf(st.delta_vs_parent.final_net_worth_real) : '–'} · {L.low}: {st.delta_vs_parent?.min_cash != null ? (st.delta_vs_parent.min_cash >= 0 ? '+' : '') + chf(st.delta_vs_parent.min_cash) : '–'}</p>
      </article>; }))}

      {sec(4, data.steps.map((st) => <div className="pr-alt" key={st.node_id}><h3>{name(st)}</h3>
        <table className="pr-table"><thead><tr><th>{L.option}</th><th>{L.nwReal}</th><th>{L.low}</th><th>{L.goals}</th><th>{L.debt}</th><th>{L.check}</th></tr></thead>
          <tbody>{row(name(st), { ...(st.summary || {}), ...summaryOf(st.result) }, true)}{st.alternatives.map((a) => row(name(a), a.summary, false))}</tbody></table></div>))}

      {sec(5, data.steps.map((st) => <div className="pr-ex" key={st.node_id}><h3>{name(st)}</h3>
        <div dangerouslySetInnerHTML={{ __html: explorationSections(st.result?.exploration, { lang, metrics: st.result?.metrics, buttons: false }) || '<p>–</p>' }} /></div>))}

      {sec(6, <table className="pr-table"><thead><tr><th /><th>{L.nwReal.replace(/ \(.*/, '')}</th><th>{L.low}</th><th>{L.shortFrom}</th><th /></tr></thead>
        <tbody>{data.stress.map((x) => { const sm = x.summary || {}; const holds = x.weather === 'none' ? sm.first_negative_month == null : sm.holds;
          return <tr key={x.weather}><th scope="row">{L.weather[x.weather] || x.weather}</th><td>{chf(sm.final_net_worth)}</td><td className={sm.min_cash < 0 ? 'neg' : ''}>{chf(sm.min_cash)}</td>
            <td>{sm.first_negative_month != null ? sm.first_negative_month + 1 : '–'}</td><td><span className={`chip ${holds ? 'ok' : 'bad'}`}>{holds ? L.holds : L.breaks}</span></td></tr>; })}</tbody></table>)}

      {sec(7, <><div dangerouslySetInnerHTML={{ __html: planCheckHTML({ ...leafRes, constraints: data.leaf.constraints, plan_check: data.leaf.plan_check }, lang, esc) }} />
        <h4>{L.surplus}</h4><Spark values={data.leaf.monthly_surplus} />{negMonths > 0 && <p className="pr-note">{L.gapLen(negMonths)}</p>}</>)}

      {sec(8, <><p className="pr-note">{L.qual}</p><ul>{[...new Set(data.steps.flatMap((st) => QUAL.filter(([re]) => re.test(st.label)).map(([, k]) => k)))].map((k) => <li key={k}>{L.q[k]}</li>)}</ul></>)}

      {sec(9, data.uncertainty ? <><dl className="pr-facts"><dt>p10</dt><dd>{chf(data.uncertainty.final_net_worth_p10)}</dd><dt>p50</dt><dd>{chf(data.uncertainty.final_net_worth_p50)}</dd>
        <dt>p90</dt><dd>{chf(data.uncertainty.final_net_worth_p90)}</dd><dt>n</dt><dd>{data.uncertainty.n_paths} · seed {data.uncertainty.seed}</dd></dl><p className="pr-note">{L.lensNote}</p></>
        : <><p className="pr-note">{L.lensOff}</p><button className="ghost no-print" onClick={() => setLens(true)}>{L.lensBtn}</button></>)}

      {sec(10, <><h4>{L.checks}</h4><ul className="pr-checks">{(data.validation.checks || []).filter((c) => c.applicable !== false).map((c) => <li key={c.name} className={c.passed ? 'ok' : 'bad'}>{c.passed ? '✓' : '✕'} {c.name.replace(/_/g, ' ')}{c.detail ? <small> · {c.detail}</small> : null}</li>)}</ul>
        <p className="pr-note">engine {data.validation.engine_version} · seed {data.validation.seed} · trace {data.validation.trace_id}</p>
        <details><summary>{L.reproduce}</summary><pre>{JSON.stringify(data.validation.reproduce, null, 2)}</pre></details></>)}

      {sec(11, <><ul>{(data.limitations || []).map((x, i) => <li key={i}>{x}</li>)}</ul><p className="pr-note">{L.responsible}</p></>)}
    </main>
  </div>;
}

function summaryOf(r) {
  const m = r?.metrics || {}, goals = r?.goals || [];
  return { final_net_worth_real: m.final_net_worth_real, min_cash: m.min_cash, final_debt: m.final_debt, goals_met: goals.filter((g) => g.met_deterministic).length, goals_total: goals.length, plan_check: r?.plan_check?.level };
}
