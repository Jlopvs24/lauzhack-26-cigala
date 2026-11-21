// Charts of the visual path report. Hand-written SVG/HTML, measured to their container so text stays at
// real pixel sizes on a phone. Rules (dataviz skill): one axis, thin marks, the chosen path is the only
// coloured series (emphasis), a funding gap is the red zone below zero, every chart has hover + focus
// tooltips and every value is also readable without hovering (direct labels, value columns or a table).
import React, { useId, useLayoutEffect, useRef, useState } from 'react';
import { chf, compact, fmtVal, signedChf } from './reportModel.js';

export function useWidth(ref, fallback = 720) {
  const [w, setW] = useState(fallback);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const update = () => setW(Math.max(260, Math.round(el.getBoundingClientRect().width)));
    update();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(update);
    ro.observe(el);
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

// One floating tooltip per chart, positioned in the chart's own box.
function useTip(boxRef) {
  const [tip, setTip] = useState(null);
  const show = (e, content) => {
    const box = boxRef.current?.getBoundingClientRect();
    if (!box) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX ?? r.left + r.width / 2) - box.left, y = (e.clientY ?? r.top) - box.top;
    setTip({ x, y, content, flip: x > box.width * 0.6 });
  };
  const el = tip && <div className="vr-tip" role="status" style={{ left: tip.x, top: tip.y, transform: `translate(${tip.flip ? 'calc(-100% - 14px)' : '14px'}, -50%)` }}>{tip.content}</div>;
  return { el, show, hide: () => setTip(null) };
}
const bindTip = (tip, content) => ({ onPointerEnter: (e) => tip.show(e, content), onPointerMove: (e) => tip.show(e, content), onPointerLeave: tip.hide, onFocus: (e) => tip.show(e, content), onBlur: tip.hide, tabIndex: 0 });

// ---------------------------------------------------------------- over time (cash / net worth)
export function TimeChart({ series, band, L, name, metricLabel, showTable = true }) {
  const box = useRef(null), w = useWidth(box);
  const clip = useId().replace(/:/g, '');
  const [hover, setHover] = useState(null);
  const narrow = w < 600;
  const H = narrow ? 230 : 290, m = { t: 14, r: narrow ? 14 : 168, b: 30, l: 46 };
  const n = Math.max(2, ...series.map((s) => s.values.length));
  const all = series.flatMap((s) => s.values).concat(band ? [...band.p10, ...band.p90] : []).filter(Number.isFinite);
  const { ticks, lo, hi } = niceTicks(Math.min(0, ...all), Math.max(0, ...all), narrow ? 4 : 5);
  const pw = w - m.l - m.r, ph = H - m.t - m.b;
  const X = (i) => m.l + (i / (n - 1)) * pw, Y = (v) => m.t + (1 - (v - lo) / (hi - lo || 1)) * ph;
  const d = (vals) => vals.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join('');
  const chosen = series.find((s) => s.chosen);
  const neg = chosen ? chosen.values.findIndex((v) => v < 0) : -1;
  const years = Math.round((n - 1) / 12);
  const yTicks = Array.from({ length: Math.floor(years / 2) + 1 }, (_, k) => k * 2);

  // direct end labels, pushed apart, with a leader when moved (desktop only)
  const ends = narrow ? [] : series.map((s) => ({ id: s.id, chosen: s.chosen, y0: Y(s.values.at(-1)), y: Y(s.values.at(-1)), text: name(s) })).sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15;
  const over = ends.length ? ends.at(-1).y - (H - m.b) : 0;
  if (over > 0) ends.forEach((e) => { e.y -= over; });

  const move = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const i = Math.round(((e.clientX - r.left) / r.width) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  };
  const key = (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    setHover((h) => Math.max(0, Math.min(n - 1, (h ?? (e.key === 'ArrowRight' ? -1 : n)) + (e.key === 'ArrowRight' ? 1 : -1) * (e.shiftKey ? 12 : 1))));
  };
  const hv = hover != null ? series.map((s) => ({ ...s, v: s.values[hover] })).sort((a, b) => b.v - a.v) : null;
  const tipLeft = hover != null && X(hover) > m.l + pw * 0.62;
  const bandPath = band?.p10?.length ? `${d(band.p90)}L${band.p10.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).reverse().join('L')}Z` : '';

  return <div className="vr-chart" ref={box}>
    <svg width={w} height={H} viewBox={`0 0 ${w} ${H}`} role="img" aria-label={metricLabel}>
      <defs><clipPath id={`neg-${clip}`}><rect x="0" y={Y(0)} width={w} height={Math.max(0, H - Y(0))} /></clipPath></defs>
      {lo < 0 && <g className="vr-gapzone">
        <rect x={m.l} y={Y(0)} width={pw} height={Math.max(0, Y(lo) - Y(0))} />
        <text x={m.l + 8} y={Y(lo) - 8}>{L.gapZone}</text>
      </g>}
      {ticks.map((t) => <g key={t} className={`vr-grid ${t === 0 ? 'zero' : ''}`}>
        <line x1={m.l} x2={m.l + pw} y1={Y(t)} y2={Y(t)} />
        <text x={m.l - 8} y={Y(t) + 4} textAnchor="end">{compact(t)}</text>
      </g>)}
      {yTicks.map((y) => <text key={y} className="vr-axis" x={X(Math.min(n - 1, y * 12))} y={H - 10} textAnchor="middle">{y}</text>)}
      {!narrow && <text className="vr-axis" x={m.l + pw + 14} y={H - 10}>{L.years}</text>}
      {bandPath && <path className="vr-band" d={bandPath} />}
      {series.filter((s) => !s.chosen).map((s) => <path key={s.id} className="vr-line sib vr-draw" pathLength="1" d={d(s.values)} />)}
      {chosen && <>
        <path className="vr-line me vr-draw" pathLength="1" d={d(chosen.values)} />
        <path className="vr-line neg vr-draw" pathLength="1" d={d(chosen.values)} clipPath={`url(#neg-${clip})`} />
        {neg >= 0 && <g className="vr-mark">
          <circle cx={X(neg)} cy={Y(chosen.values[neg])} r="4.5" />
          <text x={X(neg) + 9} y={Math.min(Y(chosen.values[neg]) + 18, Y(lo) - 24)}>{L.shortFrom(neg)}</text>
        </g>}
      </>}
      {ends.map((e) => <g key={e.id} className={`vr-end ${e.chosen ? 'me' : ''}`}>
        {Math.abs(e.y - e.y0) > 3 && <line x1={m.l + pw + 3} y1={e.y0} x2={m.l + pw + 10} y2={e.y} />}
        <text x={m.l + pw + 13} y={e.y + 4}>{e.text.length > 24 ? e.text.slice(0, 23) + '…' : e.text}</text>
      </g>)}
      {hover != null && <g className="vr-cross">
        <line x1={X(hover)} x2={X(hover)} y1={m.t} y2={m.t + ph} />
        {hv.map((s) => <circle key={s.id} className={s.chosen ? 'me' : 'sib'} cx={X(hover)} cy={Y(s.v)} r={s.chosen ? 4.5 : 3.5} />)}
      </g>}
      <rect className="vr-hit" x={m.l} y={m.t} width={pw} height={ph} tabIndex={0} aria-label={metricLabel}
        onPointerMove={move} onPointerDown={move} onPointerLeave={() => setHover(null)} onFocus={() => setHover((h) => h ?? n - 1)} onBlur={() => setHover(null)} onKeyDown={key} />
    </svg>
    {hover != null && <div className="vr-tip" style={{ left: X(hover), top: m.t + 6, transform: `translateX(${tipLeft ? 'calc(-100% - 12px)' : '12px'})` }}>
      <div className="vr-tip-h">{hover === 0 ? L.today : `${L.monthN(hover)} · ${L.yearN(Math.round((hover / 12) * 10) / 10)}`}</div>
      {hv.map((s) => <div key={s.id} className="vr-tip-row"><span className={`k ${s.chosen ? 'me' : 'sib'}`} /><b className={s.v < 0 ? 'neg' : ''}>{chf(s.v)}</b><span>{name(s)}</span></div>)}
      {band && <div className="vr-tip-row"><span className="k band" /><b>{compact(band.p10[hover])} – {compact(band.p90[hover])}</b><span>p10–p90</span></div>}
    </div>}
    <div className="vr-legend">
      <span><i className="k me" />{L.yours}</span>
      {series.length > 1 && <span><i className="k sib" />{L.others}</span>}
      {lo < 0 && <span><i className="k gap" />{L.gapZone}</span>}
      {band && <span><i className="k band" />{L.band}</span>}
    </div>
    {showTable && <details className="vr-tableview">
      <summary>{L.asTable}</summary>
      <div className="vr-scroll"><table className="vr-table">
        <thead><tr><th>{L.year}</th>{series.map((s) => <th key={s.id}>{name(s)}</th>)}</tr></thead>
        <tbody>{Array.from({ length: years + 1 }, (_, y) => <tr key={y}><th scope="row">{y}</th>
          {series.map((s) => { const v = s.values[Math.min(s.values.length - 1, y * 12)]; return <td key={s.id} className={v < 0 ? 'neg' : ''}>{chf(v)}</td>; })}</tr>)}</tbody>
      </table></div>
    </details>}
  </div>;
}

// ---------------------------------------------------------------- chosen vs alternatives, per step
const pos = (v, lo, hi) => ((v - lo) / (hi - lo || 1)) * 100;
function Bar({ v, lo, hi, cls }) {
  if (!Number.isFinite(v)) return null;
  const z = pos(0, lo, hi), p = pos(v, lo, hi);
  return <span className={`vr-bar ${cls} ${v < 0 ? 'neg' : 'pos'}`} style={{ left: `${Math.min(z, p)}%`, width: `${Math.max(0.6, Math.abs(p - z))}%` }} />;
}

export function CompareLevels({ levels, baseline, L, H, name, pin }) {
  const box = useRef(null), tip = useTip(box);
  const vals = levels.flatMap((l) => l.rows.map((r) => r.final_net_worth_real)).concat([baseline?.final_net_worth_real]).filter(Number.isFinite);
  const lo = Math.min(0, ...vals), hi = Math.max(0, ...vals), pad = (hi - lo) * 0.04;
  const [a, b] = [lo < 0 ? lo - pad : 0, hi + pad];
  const sq = baseline?.final_net_worth_real;
  return <div className="vr-compare" ref={box}>
    {levels.map((lv) => <div className="vr-level" key={lv.node_id}>
      <div className="vr-level-h"><span className="vr-stepno">{L.step(lv.step)}</span></div>
      {lv.rows.map((r) => <div className={`vr-row ${r.chosen ? 'me' : ''}`} key={r.node_id}
        {...bindTip(tip, <><div className="vr-tip-h">{name(r)}</div>
          <div className="vr-tip-row"><b>{chf(r.final_net_worth_real)}</b><span>{L.tNw}</span></div>
          <div className="vr-tip-row"><b className={r.min_cash < 0 ? 'neg' : ''}>{chf(r.min_cash)}</b><span>{L.lowest}</span></div>
          <div className="vr-tip-row"><b>{L.goalsOf(r.goals_met ?? 0, r.goals_total ?? 0)}</b><span>{L.tGoals}</span></div>
          {r.plan_check && <div className="vr-tip-row"><b>{H.level[r.plan_check] || r.plan_check}</b><span>{L.tPlan}</span></div>}</>)}>
        <span className="vr-row-name">{name(r)}{r.chosen && <em>{L.yourChoice}</em>}</span>
        <span className="vr-track">
          {lo < 0 && <span className="vr-zero" style={{ left: `${pos(0, a, b)}%` }} />}
          {Number.isFinite(sq) && <span className="vr-ref" style={{ left: `${pos(sq, a, b)}%` }} />}
          <Bar v={r.final_net_worth_real} lo={a} hi={b} cls={r.chosen ? 'me' : 'sib'} />
        </span>
        <span className="vr-row-val">{chf(r.final_net_worth_real)}</span>
        <span className="vr-row-chip">{r.first_negative_month != null && <span className="vr-chip bad sm">{L.gapChip(r.first_negative_month + 1)}</span>}{pin && <span className="vr-pin no-print">{pin(lv, r)}</span>}</span>
      </div>)}
    </div>)}
    {Number.isFinite(sq) && <p className="vr-refnote"><i className="k ref" />{name(baseline)}: {chf(sq)} · {L.statusQuo}</p>}
    {tip.el}
  </div>;
}

// ---------------------------------------------------------------- tornado
export function Tornado({ rows, L }) {
  const box = useRef(null), tip = useTip(box);
  if (!rows.length) return null;
  const xs = rows.flatMap((r) => [r.low, r.high, r.base]).filter(Number.isFinite);
  const lo0 = Math.min(...xs), hi0 = Math.max(...xs), pad = (hi0 - lo0) * 0.3 || 1;
  const lo = lo0 - pad, hi = hi0 + pad, base = rows[0].base;
  const seg = (from, to, cls) => <span className={`vr-tseg ${cls}`} style={{ left: `${pos(Math.min(from, to), lo, hi)}%`, width: `${Math.max(0.5, Math.abs(pos(to, lo, hi) - pos(from, lo, hi)))}%` }} />;
  const end = (v, val, unit) => {
    const leftSide = v < base;
    return <span className={`vr-tend ${leftSide ? 'l' : 'r'}`} style={{ left: `${pos(v, lo, hi)}%` }}>{fmtVal(val, unit)}</span>;
  };
  return <div className="vr-tornado" ref={box}>
    <div className="vr-legend vr-legend-top"><span><i className="k low" />{L.low}</span><span><i className="k high" />{L.high}</span>
      <span><i className="k base" />{L.asAssumed}: {chf(base)}</span></div>
    {rows.map((r) => <div className="vr-trow" key={r.id}
      {...bindTip(tip, <><div className="vr-tip-h">{r.label}</div>
        <div className="vr-tip-row"><span className="k low" /><b>{chf(r.low)}</b><span>{fmtVal(r.low_value, r.unit)}</span></div>
        <div className="vr-tip-row"><span className="k high" /><b>{chf(r.high)}</b><span>{fmtVal(r.high_value, r.unit)}</span></div>
        <div className="vr-tip-row"><span className="k base" /><b>{chf(r.base)}</b><span>{fmtVal(r.base_value, r.unit)}</span></div></>)}>
      <span className="vr-trow-name">{r.label}<small>{fmtVal(r.base_value, r.unit)}</small></span>
      <span className="vr-ttrack">
        <span className="vr-tbase" style={{ left: `${pos(base, lo, hi)}%` }} />
        {seg(r.base, r.low, 'low')}{seg(r.base, r.high, 'high')}
        {end(r.low, r.low_value, r.unit)}{end(r.high, r.high_value, r.unit)}
      </span>
    </div>)}
    {tip.el}
  </div>;
}

// ---------------------------------------------------------------- stress scenarios
export function StressRows({ rows, L }) {
  const box = useRef(null), tip = useTip(box);
  const vals = rows.map((r) => r.min_cash).filter(Number.isFinite);
  const lo0 = Math.min(0, ...vals), hi0 = Math.max(0, ...vals), pad = (hi0 - lo0) * 0.06 || 1;
  const lo = lo0 < 0 ? lo0 - pad : 0, hi = hi0 > 0 ? hi0 + pad : pad;
  return <div className="vr-stress" ref={box}>
    {rows.map((r) => <div className="vr-srow" key={r.key}
      {...bindTip(tip, <><div className="vr-tip-h">{r.name}</div>
        <div className="vr-tip-row"><b className={r.min_cash < 0 ? 'neg' : ''}>{chf(r.min_cash)}</b><span>{L.lowest}</span></div>
        {Number.isFinite(r.final_net_worth) && <div className="vr-tip-row"><b>{chf(r.final_net_worth)}</b><span>{L.nw} ({L.nominal})</span></div>}</>)}>
      <span className="vr-srow-name">{r.name}</span>
      <span className={`vr-chip ${r.holds ? 'good' : 'bad'}`}><span aria-hidden="true">{r.holds ? '✓' : '✕'}</span>{r.holds ? L.holds : L.breaks}</span>
      <span className="vr-track">
        <span className="vr-zero" style={{ left: `${pos(0, lo, hi)}%` }} />
        <Bar v={r.min_cash} lo={lo} hi={hi} cls="stress" />
      </span>
      <span className="vr-srow-val"><b className={r.min_cash < 0 ? 'neg' : ''}>{chf(r.min_cash)}</b><small>{r.short ? L.shortFrom(r.short) : L.neverShort}</small></span>
    </div>)}
    {tip.el}
  </div>;
}

// ---------------------------------------------------------------- constraints: pass/fail with margin
export function MarginRows({ rows, L }) {
  return <ul className="vr-limits">
    {rows.map((r) => <li key={r.name} className={r.passed ? 'ok' : 'bad'}>
      <span className="vr-pf" aria-hidden="true">{r.passed ? '✓' : '✕'}</span>
      <span className="vr-lim-name">{r.label}<small>{r.passed ? L.pass : L.fail}{r.sub ? ` · ${r.sub}` : ''}</small></span>
      <span className="vr-mtrack" aria-hidden="true"><span className="vr-mline" />
        <span className={`vr-mbar ${r.passed ? 'ok' : 'bad'}`} style={r.ratio >= 0 ? { left: '50%', width: `${Math.max(1, r.ratio * 50)}%` } : { right: '50%', width: `${Math.max(1, -r.ratio * 50)}%` }} /></span>
      <span className="vr-lim-val">{r.margin}<small>{L.margin}</small></span>
    </li>)}
  </ul>;
}

// ---------------------------------------------------------------- pillar 3a: net worth = liquid + locked
export function Pillar3aBars({ rows, L }) {
  const box = useRef(null), tip = useTip(box);
  if (!rows.length) return null;
  const lo = Math.min(0, ...rows.map((r) => r.liquid).filter(Number.isFinite));
  const hi = Math.max(...rows.map((r) => Math.max(r.nw, r.liquid + r.locked)).filter(Number.isFinite)) * 1.02 || 1;
  const seg = (from, to, cls) => <span className={`vr-p3seg ${cls}`} style={{ left: `${pos(Math.min(from, to), lo, hi)}%`, width: `${Math.max(0.4, Math.abs(pos(to, lo, hi) - pos(from, lo, hi)))}%` }} />;
  return <div className="vr-p3" ref={box}>
    <div className="vr-legend vr-legend-top"><span><i className="k liquid" />{L.p3Liquid}</span><span><i className="k locked" />{L.p3Locked}</span></div>
    {rows.map((r) => <div className={`vr-p3row ${r.key}`} key={r.key}
      {...bindTip(tip, <><div className="vr-tip-h">{r.label}</div>
        <div className="vr-tip-row"><b>{chf(r.nw)}</b><span>{L.p3Axis}</span></div>
        <div className="vr-tip-row"><span className="k liquid" /><b>{chf(r.liquid)}</b><span>{L.p3Liquid}</span></div>
        <div className="vr-tip-row"><span className="k locked" /><b>{chf(r.locked)}</b><span>{L.p3Locked}</span></div>
        {r.taxSaved > 0 && <div className="vr-tip-row"><b>{chf(r.taxSaved)}</b><span>{L.p3Tax}</span></div>}
        <div className="vr-tip-row"><b className={r.gap ? 'neg' : ''}>{chf(r.minCash)}</b><span>{L.lowest}</span></div></>)}>
      <span className="vr-p3name">{r.label}{r.gap && <span className="vr-chip bad sm">{L.p3Gap}</span>}</span>
      <span className="vr-track">
        {lo < 0 && <span className="vr-zero" style={{ left: `${pos(0, lo, hi)}%` }} />}
        {seg(0, r.liquid, r.liquid < 0 ? 'neg' : 'liquid')}
        {r.locked > 0 && seg(Math.max(0, r.liquid), Math.max(0, r.liquid) + r.locked, 'locked')}
      </span>
      <span className="vr-p3val"><b>{chf(r.nw)}</b>{r.locked > 0 && <small>{chf(r.locked)} {L.p3Locked}</small>}</span>
    </div>)}
    {tip.el}
  </div>;
}

// ---------------------------------------------------------------- 2-lever heatmap (plan level per cell)
const LEVEL_GLYPH = { holds: '✓', holds_below_target: '!', infeasible: '✕', needs_financing: '✕' };
export function Heatmap({ grid, L, H, peerName }) {
  const box = useRef(null), w = useWidth(box), tip = useTip(box);
  const nx = grid.xs.length, ny = grid.rows.length;
  const m = { l: 74, r: 8, t: 26, b: 40 };
  const cw = Math.max(26, Math.min(64, Math.floor((w - m.l - m.r) / nx))), ch = Math.min(44, cw);
  const W = m.l + nx * cw + m.r, Ht = m.t + ny * ch + m.b;
  const X = (i) => m.l + i * cw, Y = (j) => m.t + j * ch;
  const money = (v, signed) => `${signed && v > 0 ? '+' : ''}${compact(v)}`;
  // break-even: an edge between two neighbouring cells whose delta_vs_peer has opposite signs
  const edges = [];
  if (grid.hasPeer) grid.rows.forEach((r, j) => r.cells.forEach((c, i) => {
    const s = Math.sign(c.delta_vs_peer || 0), right = r.cells[i + 1], down = grid.rows[j + 1]?.cells[i];
    if (right && Math.sign(right.delta_vs_peer || 0) !== s) edges.push([X(i + 1), Y(j), X(i + 1), Y(j + 1)]);
    if (down && Math.sign(down.delta_vs_peer || 0) !== s) edges.push([X(i), Y(j + 1), X(i + 1), Y(j + 1)]);
  }));
  const plannedRow = grid.planned.y >= 0 ? ny - 1 - grid.planned.y : -1;
  return <div className="vr-heat" ref={box}>
    <svg width={W} height={Ht} viewBox={`0 0 ${W} ${Ht}`} role="img" aria-label={`${L.srTitle}: ${L.srX} × ${L.srY}`}>
      {grid.rows.map((r, j) => <g key={j}>
        <text className="vr-axis" x={m.l - 8} y={Y(j) + ch / 2 + 4} textAnchor="end">{money(r.y, true)}</text>
        {r.cells.map((c, i) => <g key={i} className={`vr-hcell ${c.level}`} tabIndex={0}
          {...bindTip(tip, <><div className="vr-tip-h">{L.srCell(money(c.x, true), money(c.y, true))}</div>
            <div className="vr-tip-row"><b>{H.level[c.level] || c.level}</b><span>{L.tPlan}</span></div>
            <div className="vr-tip-row"><b>{chf(c.final_net_worth_real)}</b><span>{L.tNw}</span></div>
            <div className="vr-tip-row"><b className={c.min_cash < 0 ? 'neg' : ''}>{chf(c.min_cash)}</b><span>{L.lowest}</span></div>
            {Number.isFinite(c.delta_vs_peer) && peerName && <div className="vr-tip-row"><b>{signedChf(c.delta_vs_peer)}</b><span>vs {peerName}</span></div>}</>)}>
          <rect x={X(i) + 1} y={Y(j) + 1} width={cw - 2} height={ch - 2} rx="4" />
          {cw >= 30 && <text x={X(i) + cw / 2} y={Y(j) + ch / 2 + 4} textAnchor="middle">{LEVEL_GLYPH[c.level] || ''}</text>}
        </g>)}
      </g>)}
      {grid.planned.x >= 0 && plannedRow >= 0 && <rect className="vr-hplanned" x={X(grid.planned.x) - 1} y={Y(plannedRow) - 1} width={cw + 2} height={ch + 2} rx="6" />}
      {edges.map((e, k) => <line key={k} className="vr-hbreak" x1={e[0]} y1={e[1]} x2={e[2]} y2={e[3]} />)}
      {grid.xs.map((x, i) => <text key={i} className="vr-axis" x={X(i) + cw / 2} y={m.t + ny * ch + 16} textAnchor="middle">{money(x, true)}</text>)}
      <text className="vr-axis" x={m.l} y={Ht - 4}>{L.srX} →</text>
      <text className="vr-axis" x={4} y={12}>{L.srY} ↑</text>
    </svg>
    <div className="vr-legend">
      {['holds', 'holds_below_target', 'needs_financing'].map((k) => <span key={k}><i className={`k lvl ${k}`} />{H.level[k]}</span>)}
      {grid.planned.x >= 0 && <span><i className="k planned" />{L.srPlanned}</span>}
      {edges.length > 0 && peerName && <span><i className="k brk" />{L.srBreak(peerName)}</span>}
    </div>
    {tip.el}
  </div>;
}

// ---------------------------------------------------------------- timing strip
export function TimingStrip({ strip, H }) {
  return <ol className="vr-tstrip">
    {strip.rows.map((r) => <li key={r.delay} className={r.tone} title={H.level[r.level] || r.level}>
      <span className="vr-tdot" aria-hidden="true">{r.tone === 'good' ? '✓' : r.tone === 'warn' ? '!' : '✕'}</span>
      <b>{r.label}</b><small>{compact(r.nw)}</small><span className="sr">{H.level[r.level] || r.level}</span>
    </li>)}
  </ol>;
}
