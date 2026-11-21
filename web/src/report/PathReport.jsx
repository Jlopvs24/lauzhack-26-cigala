// The path report ("Open your report" at a leaf): brief and visual first, every detail one click away.
// Order: hero (if… then… + 4 key numbers) → your path → money over time → alternatives → what would have
// to be true + tornado → does it hold (stress, limits) → the full report (12 spec sections, collapsed).
// It renders from /tree/expand at once, fills the what-ifs from /tree/explore, and swaps in the language
// model's wording of the summary whenever /report answers: nothing waits for the LLM.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { buildFromLevels, loadExploration, loadLevels, loadLiveValidation, loadSummary, mergeExploration } from './pathReport.js';
import { chf, compareLevels, constraintRows, fmtVal, heroTiles, pillar3a, taxSegments, oneLiner, plainTemplate, qualKeys, signedChf, stressRows, timeSeries, tornadoRows, whatIfCards } from './reportModel.js';
import { ri } from './reportI18n.js';
import { usePersonalItems } from '../personalize/YourConditions.jsx';
import { describe as describeOwn } from '../personalize/model.js';
import { H_I18N } from '../scene/headline.js';
import { CompareLevels, MarginRows, Pillar3aBars, StressRows, TimeChart, Tornado } from './charts.jsx';
import { AddToCompare } from '../compare/index.js';
import './report.css';

const TONE_ICON = { good: '✓', warn: '!', bad: '✕', neutral: '' };

function Section({ id, title, sub, children, aside, i = 0 }) {
  return <section className="vr-sec" aria-labelledby={id} style={{ '--i': i }}>
    <header className="vr-sec-h"><div><h2 id={id}>{title}</h2>{sub && <p className="vr-sub">{sub}</p>}</div>{aside}</header>
    {children}
  </section>;
}

function Disclosure({ n, title, children }) {
  return <details className="vr-disc"><summary><span className="vr-n">{String(n).padStart(2, '0')}</span>{title}<span className="vr-chev" aria-hidden="true" /></summary><div className="vr-disc-body">{children}</div></details>;
}

export default function PathReport({ lang = 'en', tr = (n) => ({ label: n.label, desc: n.description || '' }), profile, startProfile = profile, path, assumptions = [], lens = false, onClose }) {
  const L = ri(lang), H = H_I18N[lang] || H_I18N.en;
  const [data, setData] = useState(null), [error, setError] = useState(''), [attempt, setAttempt] = useState(0);
  const [lensOn, setLensOn] = useState(!!lens), [refetching, setRefetching] = useState(false);
  const [summary, setSummary] = useState(null);
  const [metric, setMetric] = useState('cash');
  const [openStep, setOpenStep] = useState(null), [trueStep, setTrueStep] = useState(null);
  const [live, setLive] = useState(null), [plainOpen, setPlainOpen] = useState(false);
  const root = useRef(null);
  const mine = usePersonalItems(); // the user's own conditions (web/src/personalize), sent with every request
  const key = JSON.stringify([path, assumptions, profile ? JSON.stringify(profile).length : 0, mine.map((it) => it.id)]);
  const ownOf = (id) => mine.filter((it) => (it.mode === 'patch' ? it.node_id === id : it.custom_node?.node_id === id));
  const name = (n) => tr({ label: n.label, description: n.description }).label;

  // stage 1 + 2: the engine's numbers (fast), then the what-ifs. A refetch keeps the previous frame.
  useEffect(() => {
    const ac = new AbortController();
    let on = true;
    setError(''); setRefetching(true);
    (async () => {
      try {
        const levels = await loadLevels({ profile, path, assumptions, uncertainty: lensOn, signal: ac.signal });
        if (!on) return;
        const d = buildFromLevels(levels, { profile, path, assumptions, uncertainty: lensOn, startProfile });
        setData(d); setRefetching(false);
        const explored = await loadExploration({ profile, path, assumptions, signal: ac.signal });
        if (on) setData((cur) => mergeExploration(cur?.leaf?.node_id === d.leaf.node_id ? cur : d, explored));
      } catch (e) {
        if (on && e.name !== 'AbortError') { setError(e.message); setRefetching(false); }
      }
    })();
    return () => { on = false; ac.abort(); };
  }, [key, lensOn, attempt]); // eslint-disable-line react-hooks/exhaustive-deps

  // stage 3: the worded summary, in the background, never awaited by the page
  useEffect(() => {
    const ac = new AbortController();
    let on = true;
    setSummary(null);
    const t = setTimeout(() => loadSummary({ profile, path, assumptions, lang, signal: ac.signal })
      .then((s) => on && setSummary(s || { failed: true })).catch(() => on && setSummary({ failed: true })), 200);
    return () => { on = false; clearTimeout(t); ac.abort(); };
  }, [key, lang]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onClose?.();
    addEventListener('keydown', k);
    root.current?.focus({ preventScroll: true });
    // Save as PDF: every disclosure open while printing, restored afterwards
    let opened = [];
    const before = () => { opened = [...(root.current?.querySelectorAll('details:not([open])') || [])]; opened.forEach((d) => { d.open = true; }); };
    const after = () => { opened.forEach((d) => { d.open = false; }); opened = []; };
    addEventListener('beforeprint', before); addEventListener('afterprint', after);
    return () => { removeEventListener('keydown', k); removeEventListener('beforeprint', before); removeEventListener('afterprint', after); };
  }, [onClose]);

  const view = useMemo(() => {
    if (!data) return null;
    const steps = data.steps;
    const ti = trueStep ?? steps.length - 1;
    return {
      line: oneLiner(data, lang, tr), tiles: heroTiles(data, lang), template: plainTemplate(data, lang, tr),
      series: timeSeries(data, metric), levels: compareLevels(data), ti,
      cards: steps.length ? whatIfCards(steps[ti], lang, tr) : [], tornado: steps.length ? tornadoRows(steps[ti]) : [], p3a: steps.length ? pillar3a(steps[ti], lang) : null,
      stress: stressRows(data, lang), limits: constraintRows(data.leaf.constraints, lang), qual: qualKeys(data),
    };
  }, [data, lang, metric, trueStep]); // eslint-disable-line react-hooks/exhaustive-deps

  const who = profile?.display_name || (profile ? L.you : 'Alexia');
  const top = <header className="vr-top">
    <span className="vr-brand">cigala</span>
    <span className="vr-top-title">{L.title}</span>
    <div className="vr-actions">
      {data && path.length > 0 && <AddToCompare path={path} label={name(data.steps.at(-1))} crumbs={data.steps.map(name)} lang={lang} />}
      <button type="button" className="vr-btn" onClick={() => print()} disabled={!data}>{L.print}</button>
      <button type="button" className="vr-btn" onClick={onClose}>{L.close}</button>
    </div>
  </header>;

  if (!data) {
    return <div className="path-report vr" role="dialog" aria-modal="true" aria-label={L.title} ref={root} tabIndex={-1}>{top}
      <main className="vr-body"><div className="vr-loading" role="status">
        {error ? <><p>{error}</p><button type="button" className="vr-btn" onClick={() => setAttempt((a) => a + 1)}>{L.retry}</button></> : <p className="vr-pulse">{L.loading}</p>}
      </div></main></div>;
  }

  const v = view, steps = data.steps, years = Math.round((data.question.horizon_months || 120) / 12);
  const useApi = summary?.text && (summary.mode === 'llm' || lang === 'en');
  const plain = useApi ? summary.text : v.template;
  const plainMeta = useApi ? (summary.mode === 'llm' ? L.plainLlm : L.plainTemplate) : summary ? L.plainTemplate : L.plainWait;
  const introduced = steps.flatMap((s) => (s.assumptions_introduced || []).map((a) => ({ ...a, by: s })));
  const introducedIds = new Set(introduced.map((a) => a.id));
  const shared = (data.assumptions || []).filter((a) => !introducedIds.has(a.id));
  const checks = (data.validation.checks || []).filter((c) => c.applicable !== false);
  const tax = taxSegments(data.leaf.tax_residence, lang, data.assumptions);
  const taxList = <ul className="vr-tax">{tax.map((g) => <li key={g.key} className={g.fallback ? 'fallback' : ''}>
    <b>{g.place}</b>{g.household && <span> · {g.household}</span>}{g.months && <small> · {g.months}</small>}
    {g.fallback && <span className="vr-chip warn sm"><span aria-hidden="true">!</span>{L.taxFallback}</span>}
    {g.unverified && <span className="vr-chip warn sm"><span aria-hidden="true">!</span>{L.notVerified}</span>}
  </li>)}</ul>;
  const runLive = () => { setLive({ running: true }); loadLiveValidation().then((r) => setLive(r)).catch(() => setLive({ na: true })); };
  const assumptionRow = (a) => <tr key={a.id}>
    <th scope="row">{a.label || a.id}{a.user_edited && <small className="vr-tag">{L.edited}</small>}</th>
    <td className="num">{fmtVal(a.value, a.unit)}</td>
    <td><span className={`vr-chip sm ${a.kind === 'observation' ? 'obs' : 'asm'}`}>{L.kinds[a.kind] || a.kind || L.kinds.assumption}</span>{' '}
      <span className={`vr-chip sm ${a.verified ? 'good' : 'warn'}`}><span aria-hidden="true">{a.verified ? '✓' : '!'}</span>{a.verified ? L.verified : L.notVerified}</span></td>
    <td className="vr-src" title={a.source || ''}><span>{a.source || '–'}</span></td>
  </tr>;

  return <div className={`path-report vr ${refetching ? 'is-refetching' : ''}`} role="dialog" aria-modal="true" aria-label={L.title} ref={root} tabIndex={-1}>{top}
    <main className="vr-body">

      {/* 1 · hero */}
      <section className="vr-hero" aria-label={L.title}>
        <p className="vr-kicker">{L.kicker(who, years)}</p>
        <ol className="vr-crumbs" aria-label={L.sPath}>
          {[data.baseline, ...steps].map((s, i) => <li key={s.node_id} className={i === 0 ? 'root' : i === steps.length ? 'leaf' : ''}>{i === 0 ? L.today : name(s)}</li>)}
        </ol>
        <h1>{v.line}</h1>
        <div className="vr-tiles">
          {v.tiles.map((t, i) => <div className={`vr-tile ${t.tone}`} key={t.key} style={{ '--i': i }}>
            <span className="vr-tile-l">{TONE_ICON[t.tone] && <span className={`vr-dot ${t.tone}`} aria-hidden="true">{TONE_ICON[t.tone]}</span>}{t.label}</span>
            <b className="vr-tile-v">{t.value}</b>
            {t.sub && <span className="vr-tile-s">{t.sub}</span>}
          </div>)}
        </div>
        <div className="vr-plain">
          <span className="vr-plain-h">{L.plainTitle}</span>
          <p key={useApi ? 'api' : 'tpl'} className={`vr-swap ${plain.length > 300 && !plainOpen ? 'clamp' : ''}`}>{plain}</p>
          <div className="vr-plain-foot">
            <span className={`vr-plain-meta ${!summary ? 'vr-pulse' : ''}`}>{plainMeta}</span>
            {plain.length > 300 && <button type="button" className="vr-link" aria-expanded={plainOpen} onClick={() => setPlainOpen((o) => !o)}>{plainOpen ? L.less : L.more}</button>}
          </div>
        </div>
      </section>

      {/* 4 · your path */}
      <Section id="vr-path" title={L.sPath} sub={L.sPathSub} i={1}>
        <ol className="vr-stepper">
          <li className="vr-node root">
            <span className="vr-node-dot" aria-hidden="true" />
            <div className="vr-node-card">
              <span className="vr-stepno">{L.today}</span>
              <b>{name(data.baseline)}</b>
              <span className="vr-node-d">{L.statusQuo}: {chf(data.baseline.summary.final_net_worth_real)}</span>
              {data.baseline.summary.first_negative_month != null && <span className="vr-chip bad sm">{L.gapChip(data.baseline.summary.first_negative_month + 1)}</span>}
            </div>
          </li>
          {steps.map((s, i) => {
            const dn = s.delta_vs_parent?.final_net_worth_real, open = openStep === i, own = ownOf(s.node_id);
            const custom = s.custom || own.some((it) => it.mode === 'branch');
            return <li className={`vr-node ${open ? 'open' : ''} ${i === steps.length - 1 ? 'leaf' : ''} ${custom ? 'custom' : ''}`} key={s.node_id}>
              <span className="vr-node-dot" aria-hidden="true" />
              <button type="button" className="vr-node-card" aria-expanded={open} aria-controls="vr-step-detail" onClick={() => setOpenStep(open ? null : i)}>
                <span className="vr-stepno">{L.step(i + 1)}</span>
                <b>{name(s)}</b>
                <span className="vr-node-d">{tr(s).desc}</span>
                <span className="vr-node-chips">
                  <span className={`vr-delta ${!Number.isFinite(dn) || Math.abs(dn) < 0.5 ? 'flat' : dn > 0 ? 'up' : 'down'}`}>
                    <span aria-hidden="true">{!Number.isFinite(dn) || Math.abs(dn) < 0.5 ? '→' : dn > 0 ? '▲' : '▼'}</span>
                    {Number.isFinite(dn) && Math.abs(dn) >= 0.5 ? `${signedChf(dn)} ${L.nwShort}` : L.noChange}</span>
                  {s.summary.first_negative_month != null && <span className="vr-chip bad sm">{L.gapChip(s.summary.first_negative_month + 1)}</span>}
                  {custom && <span className="vr-chip own sm">{L.yourBranch}</span>}
                  {own.filter((it) => it.mode === 'patch').map((it) => <span key={it.id} className="vr-chip own sm" title={it.label}>{L.yourCond}: {it.label}</span>)}
                </span>
                <span className="vr-node-more">{open ? L.hideDetail : L.showDetail}</span>
              </button>
            </li>;
          })}
        </ol>
        {openStep != null && steps[openStep] && <div className="vr-step-detail" id="vr-step-detail">
          <div>
            {ownOf(steps[openStep].node_id).length > 0 && <><h3>{L.aYours}</h3><ul className="vr-own-l">{ownOf(steps[openStep].node_id).flatMap((it) => (it.interventions || []).map((iv, j) => <li key={it.id + j}>{describeOwn(iv, lang)}</li>))}</ul></>}
            <h3>{L.changes}</h3>
            {steps[openStep].changes?.length ? <ul>{steps[openStep].changes.map((c, i) => <li key={i}>{c}</li>)}</ul> : <p className="vr-muted">{L.none}</p>}
          </div>
          <div>
            <h3>{L.introduced}</h3>
            {steps[openStep].assumptions_introduced?.length ? <ul>{steps[openStep].assumptions_introduced.map((a) => <li key={a.id}>{a.label}: <b>{fmtVal(a.value, a.unit)}</b>
              <small> · {L.kinds[a.kind] || a.kind} · {a.verified ? L.verified : L.notVerified}</small></li>)}</ul> : <p className="vr-muted">{L.none}</p>}
            <h3>{L.vsBefore}</h3>
            <p className="vr-kv"><span>{L.tNw}</span><b>{signedChf(steps[openStep].delta_vs_parent?.final_net_worth_real)}</b></p>
            <p className="vr-kv"><span>{L.lowest}</span><b>{signedChf(steps[openStep].delta_vs_parent?.min_cash)}</b></p>
          </div>
        </div>}
      </Section>

      {/* money over time, chosen vs siblings at the leaf level (+ the lens band when on) */}
      <Section id="vr-time" title={L.sTime} sub={L.sTimeSub} i={2}
        aside={<div className="vr-seg" role="group" aria-label={L.sTime}>
          {['cash', 'nw'].map((k) => <button type="button" key={k} aria-pressed={metric === k} onClick={() => setMetric(k)}>{k === 'cash' ? L.cash : L.nw}</button>)}
        </div>}>
        <p className="vr-unit">{metric === 'cash' ? L.cash : L.nw} · {L.nominal}</p>
        <TimeChart key={metric} series={v.series} band={data.leaf.bands ? (metric === 'cash' ? data.leaf.bands.cash : data.leaf.bands.net_worth) : null}
          L={L} name={name} metricLabel={`${metric === 'cash' ? L.cash : L.nw} (${L.nominal})`} />
      </Section>

      {/* 5 · alternatives at every level */}
      {v.levels.length > 0 && <Section id="vr-alt" title={L.sAlt} sub={L.sAltSub} i={3}>
        <CompareLevels levels={v.levels} baseline={{ ...data.baseline, ...data.baseline.summary }} L={L} H={H} name={name}
          pin={(lv, r) => <AddToCompare path={[...path.slice(0, lv.step - 1), r.node_id]} label={name(r)} lang={lang} variant="icon" />} />
      </Section>}

      {/* 6 · what would have to be true + tornado */}
      {steps.length > 0 && <Section id="vr-true" title={L.sTrue} sub={L.sTrueSub} i={4}
        aside={steps.length > 1 && <div className="vr-seg" role="group" aria-label={L.sTrue}>
          {steps.map((s, i) => <button type="button" key={s.node_id} aria-pressed={v.ti === i} onClick={() => setTrueStep(i)} title={name(s)}>{L.step(i + 1)}</button>)}
        </div>}>
        {steps.length > 1 && <p className="vr-unit">{name(steps[v.ti])}</p>}
        {!data.explored && !v.cards.length ? <div className="vr-cards ghost" aria-busy="true"><p className="vr-pulse">{L.computing}</p></div>
          : <div className="vr-cards">
            {v.cards.map((c, i) => <article className={`vr-card ${c.tone}`} key={c.key} style={{ '--i': i }}>
              <h3>{c.title}</h3>
              <b className="vr-card-big">{c.big}</b>
              <p>{c.text}</p>
              {!!c.more?.length && <ul>{c.more.map((x, j) => <li key={j}>{x}</li>)}</ul>}
            </article>)}
          </div>}
        {v.p3a && <article className="vr-p3card" aria-labelledby="vr-p3-h">
          <h3 id="vr-p3-h" className="vr-h3">{L.p3Title}</h3>
          {v.p3a.status === 'no_earned_income' ? <p className="vr-sub">{v.p3a.text}</p> : <>
            <p className="vr-sub">{v.p3a.lead}</p>
            <Pillar3aBars rows={v.p3a.rows} L={L} />
            {v.p3a.caveat && <p className="vr-p3note"><span className="vr-p3lock" aria-hidden="true" />{v.p3a.caveat}</p>}
            {v.p3a.seek && <p className="vr-muted vr-p3seek">{v.p3a.seek}</p>}
          </>}
        </article>}
        {v.tornado.length > 0 && <div className="vr-subsec">
          <h3 className="vr-h3">{L.sTornado}</h3>
          <p className="vr-sub">{L.sTornadoSub}</p>
          <Tornado rows={v.tornado} L={L} />
        </div>}
      </Section>}

      {/* 7 + 8 · does it hold */}
      <Section id="vr-hold" title={L.sHold} i={5}>
        <div className="vr-two">
          <div>
            <h3 className="vr-h3">{L.sStress}</h3>
            <p className="vr-sub">{L.sStressSub}</p>
            <StressRows rows={v.stress} L={L} />
          </div>
          <div>
            <h3 className="vr-h3">{L.sLimits}</h3>
            <p className="vr-sub">{L.sLimitsSub}</p>
            <MarginRows rows={v.limits} L={L} />
          </div>
        </div>
      </Section>

      {/* the full report: every remaining spec section, collapsed */}
      <Section id="vr-more" title={L.sMore} sub={L.sMoreSub} i={6}>
        <div className="vr-discs">
          <Disclosure n={2} title={L.dScope}>
            <dl className="vr-dl">
              <dt>{L.question}</dt><dd>{[data.baseline, ...steps].map(name).join(' → ')}</dd>
              <dt>{L.horizon}</dt><dd>{L.months(data.question.horizon_months)}</dd>
              <dt>{L.currency}</dt><dd>{data.question.currency}</dd>
              <dt>{L.where}</dt><dd>{tax.length ? taxList : data.question.jurisdiction}</dd>
              <dt>{L.asOf}</dt><dd>{data.question.as_of}</dd>
              <dt>{L.values}</dt><dd>{L.valuesText}</dd>
            </dl>
          </Disclosure>
          <Disclosure n={3} title={L.dStart}>
            {data.starting_state.length ? <div className="vr-scroll"><table className="vr-table">
              <thead><tr><th>{L.field}</th><th>{L.value}</th><th>{L.origin}</th></tr></thead>
              <tbody>{data.starting_state.map((f) => <tr key={f.field}><th scope="row">{f.field.replace(/_/g, ' ')}</th>
                <td className="num">{typeof f.value === 'number' ? (/age|month/.test(f.field) ? f.value : chf(f.value)) : Array.isArray(f.value) ? f.value.length : String(f.value ?? '–')}</td>
                <td><span className={`vr-chip sm ${f.label === 'synthetic' ? 'asm' : 'obs'}`}>{L.origins[f.label] || f.label}</span> <small className="vr-muted">{f.source || ''}</small></td></tr>)}</tbody>
            </table></div> : <p className="vr-muted">–</p>}
          </Disclosure>
          <Disclosure n={4} title={L.dAssume}>
            {tax.length > 0 && <><h4>{L.taxTitle}</h4>{taxList}</>}
            {mine.length > 0 && <><h4>{L.aYours}</h4><ul className="vr-own">{mine.map((it) => <li key={it.id}>
              <span className={`vr-chip sm ${it.mode === 'branch' ? 'own solid' : 'own'}`}>{it.mode === 'branch' ? L.yourBranch : L.yourCond}</span>
              <span><b>{it.label}</b>{it.mode === 'patch' ? <small> · {(() => { const st = [data.baseline, ...steps].find((x) => x.node_id === it.node_id); return st ? name(st) : it.node_label; })()}</small> : null}
                <small className="vr-own-d">{(it.interventions || []).map((iv) => describeOwn(iv, lang)).join(' · ')}{it.text ? ` · “${it.text}”` : ''}</small></span>
            </li>)}</ul></>}
            {introduced.length > 0 && <><h4>{L.aPath}</h4><div className="vr-scroll"><table className="vr-table vr-atable">
              <thead><tr><th>{L.aName}</th><th>{L.value}</th><th>{L.aKind}</th><th>{L.aSource}</th></tr></thead>
              <tbody>{introduced.map(assumptionRow)}</tbody></table></div></>}
            {shared.length > 0 && <><h4>{L.aAll}</h4><div className="vr-scroll"><table className="vr-table vr-atable">
              <thead><tr><th>{L.aName}</th><th>{L.value}</th><th>{L.aKind}</th><th>{L.aSource}</th></tr></thead>
              <tbody>{shared.map(assumptionRow)}</tbody></table></div></>}
          </Disclosure>
          <Disclosure n={9} title={L.dQual}>
            <p className="vr-muted">{L.qualNote}</p>
            <ul>{v.qual.map((k) => <li key={k}>{L.qual[k]}</li>)}</ul>
          </Disclosure>
          <Disclosure n={10} title={L.dLens}>
            {data.uncertainty ? <>
              <div className="vr-mini">
                <div><span>{L.p10}</span><b>{chf(data.uncertainty.final_net_worth_p10)}</b></div>
                <div><span>{L.p50}</span><b>{chf(data.uncertainty.final_net_worth_p50)}</b></div>
                <div><span>{L.p90}</span><b>{chf(data.uncertainty.final_net_worth_p90)}</b></div>
                {Number.isFinite(data.uncertainty.shortfall_probability) && <div><span>{L.shortShare}</span><b>{Math.round(data.uncertainty.shortfall_probability * 100)}%</b></div>}
              </div>
              <p className="vr-muted">{L.lensNote(data.uncertainty.n_paths, data.uncertainty.seed)}</p>
            </> : <><p className="vr-muted">{lensOn && refetching ? L.lensLoading : L.lensOff}</p>
              {!lensOn && <button type="button" className="vr-btn no-print" onClick={() => setLensOn(true)}>{L.lensBtn}</button>}</>}
          </Disclosure>
          <Disclosure n={11} title={L.dValid}>
            <p className="vr-checksum"><span className={`vr-chip ${checks.every((c) => c.passed) ? 'good' : 'bad'}`}><span aria-hidden="true">{checks.every((c) => c.passed) ? '✓' : '✕'}</span>{L.checksRun(checks.filter((c) => c.passed).length, checks.length)}</span></p>
            <ul className="vr-checks">{checks.map((c) => <li key={c.name} className={c.passed ? 'ok' : 'bad'}><span aria-hidden="true">{c.passed ? '✓' : '✕'}</span>
              <span>{c.name.replace(/_/g, ' ')}{c.detail && <small> · {c.detail}</small>}</span></li>)}</ul>
            <dl className="vr-dl"><dt>{L.engine}</dt><dd>{data.validation.engine_version}</dd><dt>{L.seed}</dt><dd>{data.validation.seed}</dd><dt>{L.trace}</dt><dd><code>{data.validation.trace_id}</code></dd></dl>
            <div className="vr-live no-print">
              {!live && <button type="button" className="vr-btn" onClick={runLive}>{L.live}</button>}
              {live?.running && <p className="vr-pulse vr-muted">{L.liveRunning}</p>}
              {live?.na && <p className="vr-muted">{L.liveNa}</p>}
              {live?.checks && <><p><span className={`vr-chip ${live.all_passed ? 'good' : 'bad'}`}><span aria-hidden="true">{live.all_passed ? '✓' : '✕'}</span>{L.livePassed(live.passed, live.total, Math.round(live.duration_ms))}</span></p>
                <ul className="vr-checks">{live.checks.map((c) => <li key={c.id} className={c.passed ? 'ok' : 'bad'}><span aria-hidden="true">{c.passed ? '✓' : '✕'}</span><span>{c.label}{c.detail && <small> · {c.detail}</small>}</span></li>)}</ul></>}
            </div>
            {summary?.testEvidence?.length > 0 && <details className="vr-inner"><summary>{L.evidence}</summary><ul className="vr-mono">{summary.testEvidence.map((t, i) => <li key={i}>{t.file} · {t.test}</li>)}</ul></details>}
            <details className="vr-inner"><summary>{L.reproduce}</summary><pre>{JSON.stringify(data.validation.reproduce, null, 2)}</pre></details>
          </Disclosure>
          <Disclosure n={12} title={L.dLimits}>
            <ul>{L.limits.map((x, i) => <li key={i}>{x}</li>)}</ul>
            <p className="vr-muted">{L.responsible}</p>
          </Disclosure>
        </div>
      </Section>

      <footer className="vr-foot"><span>{L.footer}</span><span>{data.engine_version} · {data.validation.trace_id}</span></footer>
    </main>
  </div>;
}

