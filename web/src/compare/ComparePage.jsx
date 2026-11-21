// The comparison page, laid out like a product spec comparator: one column per path (up to 4), rows
// grouped by section, highest / lowest marked per row (never "best"), "show only differences", and an
// overlay chart of net worth (or cash) over time on top. Desktop: full-screen sheet; phone: bottom sheet.
import React, { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { buildComparison, onlyDifferences, seriesOf, pathKey } from './model.js';
import { loadComparison } from './data.js';
import { ci, chf, chfK } from './i18n.js';
import { H_I18N } from '../scene/headline.js';
import { W_I18N } from '../weather/weatherI18n.js';
import { AddToCompare } from './Compare.jsx';

const ICON = { good: '✓', warn: '!', bad: '✕', none: '' };

function useWidth(ref) {
  const [w, setW] = useState(720);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const up = () => setW(Math.max(260, Math.round(el.getBoundingClientRect().width)));
    up();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(up); ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return w;
}
function niceTicks(lo, hi, n = 4) {
  const span = hi - lo || Math.abs(hi) || 1, raw = span / n, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => s >= raw);
  const a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step, ticks = [];
  for (let v = a; v <= b + step / 2; v += step) ticks.push(Math.round(v / step) * step);
  return { ticks, lo: a, hi: b };
}
const compact = (v) => chfK(v).replace('CHF ', '');

// Overlay of up to 4 paths, one categorical hue each (fixed order = column order), direct end labels,
// the funding-gap zone below zero, a crosshair tooltip (pointer + arrow keys) and a table view.
function OverlayChart({ series, L, title }) {
  const box = useRef(null), w = useWidth(box), clip = useId().replace(/:/g, '');
  const [hover, setHover] = useState(null);
  const narrow = w < 560;
  const H = narrow ? 220 : 280, m = { t: 12, r: narrow ? 12 : 170, b: 28, l: 44 };
  const n = Math.max(2, ...series.map((s) => s.values.length));
  const all = series.flatMap((s) => s.values).filter(Number.isFinite);
  const { ticks, lo, hi } = niceTicks(Math.min(0, ...all), Math.max(0, ...all), narrow ? 4 : 5);
  const pw = w - m.l - m.r, ph = H - m.t - m.b;
  const X = (i) => m.l + (i / (n - 1)) * pw, Y = (v) => m.t + (1 - (v - lo) / (hi - lo || 1)) * ph;
  const d = (vals) => vals.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join('');
  const years = Math.round((n - 1) / 12);
  const ends = narrow ? [] : series.filter((s) => s.values.length).map((s) => ({ key: s.key, slot: s.slot, y0: Y(s.values.at(-1)), y: Y(s.values.at(-1)), text: s.label })).sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15;
  const over = ends.length ? ends.at(-1).y - (H - m.b) : 0;
  if (over > 0) ends.forEach((e) => { e.y -= over; });
  const move = (e) => { const r = e.currentTarget.getBoundingClientRect(); setHover(Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width) * (n - 1))))); };
  const key = (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const dir = e.key === 'ArrowRight' ? 1 : -1;
    setHover((h) => Math.max(0, Math.min(n - 1, (h ?? (dir > 0 ? -1 : n)) + dir * (e.shiftKey ? 12 : 1))));
  };
  const hv = hover != null ? series.map((s) => ({ ...s, v: s.values[hover] })).filter((s) => Number.isFinite(s.v)).sort((a, b) => b.v - a.v) : null;
  const tipLeft = hover != null && X(hover) > m.l + pw * 0.6;
  return <div className="cmp-chart" ref={box}>
    <svg width={w} height={H} viewBox={`0 0 ${w} ${H}`} role="img" aria-label={title}>
      <defs><clipPath id={`g-${clip}`}><rect x="0" y={Y(0)} width={w} height={Math.max(0, H - Y(0))} /></clipPath></defs>
      {lo < 0 && <g className="cmp-gapzone"><rect x={m.l} y={Y(0)} width={pw} height={Math.max(0, Y(lo) - Y(0))} /><text x={m.l + 8} y={Y(lo) - 7}>{L.gapZone}</text></g>}
      {ticks.map((t) => <g key={t} className={`cmp-grid ${t === 0 ? 'zero' : ''}`}><line x1={m.l} x2={m.l + pw} y1={Y(t)} y2={Y(t)} /><text x={m.l - 8} y={Y(t) + 4} textAnchor="end">{compact(t)}</text></g>)}
      {Array.from({ length: Math.floor(years / 2) + 1 }, (_, k) => k * 2).map((y) => <text key={y} className="cmp-axis" x={X(Math.min(n - 1, y * 12))} y={H - 9} textAnchor="middle">{y}</text>)}
      {!narrow && <text className="cmp-axis" x={m.l + pw + 12} y={H - 9}>{L.years}</text>}
      {series.map((s) => s.values.length > 1 && <g key={s.key} className={`cmp-line s${s.slot + 1}`}>
        <path className="cmp-draw" pathLength="1" d={d(s.values)} />
        <path className="neg" d={d(s.values)} clipPath={`url(#g-${clip})`} />
      </g>)}
      {ends.map((e) => <g key={e.key} className={`cmp-end s${e.slot + 1}`}>
        {Math.abs(e.y - e.y0) > 3 && <line x1={m.l + pw + 3} y1={e.y0} x2={m.l + pw + 9} y2={e.y} />}
        <circle cx={m.l + pw + 15} cy={e.y} r="4" />
        <text x={m.l + pw + 23} y={e.y + 4}>{e.text.length > 20 ? e.text.slice(0, 19) + '…' : e.text}</text>
      </g>)}
      {hover != null && <g className="cmp-cross"><line x1={X(hover)} x2={X(hover)} y1={m.t} y2={m.t + ph} />
        {hv.map((s) => <circle key={s.key} className={`s${s.slot + 1}`} cx={X(hover)} cy={Y(s.v)} r="4.5" />)}</g>}
      <rect className="cmp-hit" x={m.l} y={m.t} width={pw} height={ph} tabIndex={0} aria-label={title}
        onPointerMove={move} onPointerDown={move} onPointerLeave={() => setHover(null)} onFocus={() => setHover((h) => h ?? n - 1)} onBlur={() => setHover(null)} onKeyDown={key} />
    </svg>
    {hover != null && <div className="cmp-tip" role="status" style={{ left: X(hover), top: m.t + 4, transform: `translateX(${tipLeft ? 'calc(-100% - 12px)' : '12px'})` }}>
      <div className="cmp-tip-h">{hover === 0 ? L.today : `${L.monthN(hover)} · ${L.yearN(Math.round((hover / 12) * 10) / 10)}`}</div>
      {hv.map((s) => <div key={s.key} className="cmp-tip-row"><i className={`cmp-swatch s${s.slot + 1}`} /><b className={s.v < 0 ? 'neg' : ''}>{chf(s.v)}</b><span>{s.label}</span></div>)}
    </div>}
    <div className="cmp-legend">{series.map((s) => <span key={s.key} className={`s${s.slot + 1}`}><i className="cmp-swatch" />{s.label}</span>)}
      {lo < 0 && <span><i className="cmp-swatch gap" />{L.gapZone}</span>}</div>
    <details className="cmp-tableview"><summary>{L.asTable}</summary>
      <div className="cmp-scroll"><table className="cmp-mini"><thead><tr><th scope="col">{L.year}</th>{series.map((s) => <th scope="col" key={s.key}>{s.label}</th>)}</tr></thead>
        <tbody>{Array.from({ length: years + 1 }, (_, y) => <tr key={y}><th scope="row">{y}</th>
          {series.map((s) => { const v = s.values[Math.min(s.values.length - 1, y * 12)]; return <td key={s.key} className={v < 0 ? 'neg' : ''}>{chf(v)}</td>; })}</tr>)}</tbody></table></div>
    </details>
  </div>;
}

export default function ComparePage({ lang = 'en', tr, paths = [], source = 'pinned', profile, assumptions = [], weather = [], fields = {}, onClose, onRemove }) {
  const L = ci(lang), H = H_I18N[lang] || H_I18N.en, W = W_I18N[lang] || W_I18N.en;
  const label = (id, l) => (tr ? tr({ node_id: id, label: l }).label || l : l);
  const [cols, setCols] = useState(null), [error, setError] = useState(''), [attempt, setAttempt] = useState(0), [pending, setPending] = useState(false);
  const [diffOnly, setDiffOnly] = useState(false), [metric, setMetric] = useState('net_worth_real');
  const root = useRef(null), closeRef = useRef(null), opener = useRef(typeof document !== 'undefined' ? document.activeElement : null);
  const keys = paths.map(pathKey).join('|');
  const reqKey = JSON.stringify([keys, profile ? JSON.stringify(profile).length : 0, assumptions, weather, fields, attempt]);

  useEffect(() => {
    if (!paths.length) { setCols([]); return undefined; }
    const ctl = new AbortController();
    setError(''); setPending(true);
    loadComparison({ paths, profile, assumptions, weather, fields, signal: ctl.signal, onPartial: (c) => { if (!ctl.signal.aborted) setCols(c); } })
      .then((c) => { if (!ctl.signal.aborted) setCols(c); })
      .catch((e) => { if (!ctl.signal.aborted && e.name !== 'AbortError') setError(L.error); })
      .finally(() => { if (!ctl.signal.aborted) setPending(false); });
    return () => ctl.abort();
  }, [reqKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // focus in, Esc closes, focus back to the opener on close; background does not scroll
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); onClose?.(); } };
    addEventListener('keydown', onKey, true);
    const prev = document.body.style.overflow; document.body.style.overflow = 'hidden';
    const op = opener.current;
    return () => { removeEventListener('keydown', onKey, true); document.body.style.overflow = prev; op?.focus?.(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // keep columns in the order of `paths` (removals apply at once, before any refetch)
  const [removed, setRemoved] = useState(() => new Set());
  const shown = useMemo(() => (cols || []).filter((c) => !removed.has(c.key) && (paths.length === 1 || paths.some((p) => pathKey(p) === c.key)))
    .map((c) => ({ ...c, label: label(c.node_id, c.label) })), [cols, keys, lang, removed]); // eslint-disable-line react-hooks/exhaustive-deps
  const cmp = useMemo(() => buildComparison(shown, { lang, label, weatherLabel: (t) => W.names?.[t] || t.replace(/_/g, ' ') }), [shown, lang]); // eslint-disable-line react-hooks/exhaustive-deps
  const sections = diffOnly ? onlyDifferences(cmp.sections) : cmp.sections;
  const series = seriesOf(shown, metric);
  const levelText = (lv) => H.level[lv] || lv || '–';
  const weatherText = (weather || []).map((w) => W.names?.[w.type || w] || w.type || w).join(', ');

  return <div className="cmp" role="dialog" aria-modal="true" aria-labelledby="cmp-title" ref={root}>
    <div className="cmp-scrim" onClick={onClose} aria-hidden="true" />
    <div className={`cmp-sheet ${pending && cols ? 'is-refetching' : ''}`}>
      <header className="cmp-top">
        <span className="cmp-grab" aria-hidden="true" />
        <div className="cmp-top-text">
          <h2 id="cmp-title">{source === 'options' ? L.titleOptions : paths.length === 1 ? L.titleAlternatives : L.title}</h2>
          <p className="cmp-lede">{L.lede}</p>
        </div>
        <div className="cmp-top-actions">
          <label className="cmp-switch"><input type="checkbox" checked={diffOnly} onChange={(e) => setDiffOnly(e.target.checked)} /><span className="cmp-switch-ui" aria-hidden="true" />{L.onlyDiff}</label>
          <button type="button" className="cmp-close" ref={closeRef} onClick={onClose} aria-label={L.close}>×</button>
        </div>
      </header>

      <div className="cmp-body">
        {error && <div className="cmp-error" role="alert">{error}<button type="button" onClick={() => setAttempt((a) => a + 1)}>{L.retry}</button></div>}
        {!cols && !error && <div className="cmp-loading" role="status"><span className="cmp-pulse">{L.loading}</span></div>}
        {cols && <>
          <section className="cmp-sec cmp-over" aria-labelledby="cmp-over-h">
            <div className="cmp-sec-h"><h3 id="cmp-over-h">{L.overTime}</h3>
              <div className="cmp-seg" role="group" aria-label={L.overTime}>
                {[['net_worth_real', L.nwReal], ['cash', L.cash]].map(([k, t]) => <button key={k} type="button" aria-pressed={metric === k} onClick={() => setMetric(k)}>{t}</button>)}
              </div></div>
            {series.length ? <OverlayChart series={series} L={L} title={`${L.overTime}: ${metric === 'cash' ? L.cash : L.nwReal}`} /> : null}
          </section>

          <div className="cmp-scroll cmp-table-wrap" style={{ '--cols': Math.max(1, cmp.columns.length) }}>
            <table className="cmp-table">
              <thead><tr>
                <td className="cmp-corner" />
                {cmp.columns.map((c, i) => <th key={c.key} scope="col" className={`cmp-col s${i + 1}`}>
                  <span className="cmp-col-bar" aria-hidden="true" />
                  <ol className="cmp-crumbs" aria-label="Path">{c.crumbs.slice(0, -1).map((k) => <li key={k.id}>{label(k.id, k.label)}</li>)}</ol>
                  <span className="cmp-col-name">{c.label}</span>
                  <span className={`cmp-badge ${c.tone}`}><b aria-hidden="true">{ICON[c.tone]}</b>{levelText(c.level)}</span>
                  <span className="cmp-col-actions">
                    {(source === 'options' || paths.length === 1) && <AddToCompare path={shown[i].path} label={c.label} lang={lang} variant="icon" />}
                    {cmp.columns.length > 1 && <button type="button" className="cmp-x" aria-label={L.colRemove(c.label)} onClick={() => { setRemoved((r) => new Set(r).add(c.key)); if (paths.length > 1 || source !== 'pinned') onRemove?.(c.key); }}>×</button>}
                  </span>
                </th>)}
              </tr></thead>
              {sections.map((s) => <tbody key={s.key} className={`cmp-group g-${s.key}`}>
                <tr className="cmp-group-h"><th scope="colgroup" colSpan={cmp.columns.length + 1}>{s.title}</th></tr>
                {s.rows.map((r) => <tr key={r.key}>
                  <th scope="row">{r.label}</th>
                  {r.cells.map((c, i) => <td key={i} className={`${c.mark || ''} ${c.tone ? 'tone-' + c.tone : ''}`}>
                    {r.key === 'plan' ? <span className={`cmp-badge ${c.tone}`}><b aria-hidden="true">{ICON[c.tone]}</b>{levelText(c.level)}</span> : <span className="cmp-val">{c.text}</span>}
                    {c.mark && <small className="cmp-mark">{c.mark === 'hi' ? L.highest : L.lowest}</small>}
                  </td>)}
                </tr>)}
              </tbody>)}
            </table>
          </div>
          {cmp.columns.length < 2 && <p className="cmp-note">{L.needTwo}. {L.pinnedHint}</p>}
          <p className="cmp-note">{L.condition}{weatherText ? ` ${L.weatherOn(weatherText)}.` : ''}{source === 'options' ? ` ${L.pinnedHint}` : ''}</p>
        </>}
      </div>
    </div>
  </div>;
}
