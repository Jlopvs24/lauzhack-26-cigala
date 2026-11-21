// Left weather rail (#87). The engine owns every magnitude and every result.
import React, { useEffect, useId, useRef, useState } from 'react';
import { M_I18N, W_I18N } from './weatherI18n.js';
import { MACRO_CLEAR, FACTORS, SCENARIOS, buildMacroWeather, macroOptions, selectScenario, toggleFactor } from './weatherModel.js';
import './weather.css';

const ICON = {
  pessimistic: 'M4 15a4 4 0 0 1 1-8 6 6 0 0 1 11 1 3.5 3.5 0 0 1 1 7H4m3 2-1 3m5-3-1 3m5-3-1 3',
  neutral: 'M12 3v2M5 6l1 1m12-1-1 1M4 12H2m20 0h-2M9 15a5 5 0 1 1 8-5M5 20h13a3 3 0 0 0 0-6 5 5 0 0 0-9-1 3.5 3.5 0 0 0-4 7',
  optimistic: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8m0-6v2m0 16v2M2 12h2m16 0h2M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2',
  plus: 'M12 5v14M5 12h14', close: 'm6 6 12 12M18 6 6 18',
};
const Icon = ({ type }) => <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d={ICON[type]} /></svg>;

export default function WeatherControl({ lang = 'en', tree, busy = false, onChange }) {
  const L = M_I18N[lang] || M_I18N.en;
  const W = W_I18N[lang] || W_I18N.en;
  const [sel, setSel] = useState(MACRO_CLEAR), [open, setOpen] = useState(false);
  const root = useRef(null), more = useRef(null);
  const id = useId();
  useEffect(() => {
    const dock = document.querySelector('.chatp-dock-wrap');
    const place = () => {
      const rect = dock?.getBoundingClientRect();
      const bottom = rect?.height ? Math.max(96, innerHeight - rect.top + 12) : 96;
      root.current?.style.setProperty('--wx-phone-bottom', `${bottom}px`);
    };
    const observer = new ResizeObserver(place);
    if (dock) observer.observe(dock);
    addEventListener('resize', place); place();
    return () => { observer.disconnect(); removeEventListener('resize', place); };
  }, []);
  useEffect(() => {
    if (!open) return;
    const outside = (e) => { if (!root.current?.contains(e.target)) setOpen(false); };
    const escape = (e) => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); setOpen(false); more.current?.focus(); } };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, [open]);
  const commit = (next) => { setSel(next); onChange?.(buildMacroWeather(next)); };
  if (!macroOptions(tree, 'scenario').length) return null;
  return <aside className="wx-rail" ref={root} aria-label={L.title} data-layout-obstacle>
    <div className="wx-perspectives" role="group" aria-label={L.title}>
      {SCENARIOS.map((level) => <button key={level} type="button" className="wx-icon" disabled={busy}
        aria-label={L.labels[`scenario:${level}`]} aria-describedby={`${id}-${level}`} aria-pressed={sel.scenario === level}
        onClick={() => commit(selectScenario(level))}>
        <Icon type={level} /><span className="wx-tip" aria-hidden="true">{L.labels[`scenario:${level}`]}</span>
        <span className="sr-only" id={`${id}-${level}`}>{L.descriptions[level]}</span>
      </button>)}
    </div>
    <button ref={more} type="button" className="wx-icon wx-more" aria-label={open ? L.close : L.more}
      aria-expanded={open} aria-controls={`${id}-factors`} onClick={() => setOpen(!open)}>
      <Icon type={open ? 'close' : 'plus'} />
      <span className="wx-tip" aria-hidden="true">{open ? L.close : L.more}</span>
      {!!Object.keys(sel.factors).length && <span className="wx-custom" aria-hidden="true" />}
    </button>
    <span className="sr-only" role="status" aria-live="polite">{busy ? W.recomputing : L.condition(
      [L.labels[`scenario:${sel.scenario}`], ...Object.entries(sel.factors).map(([type, level]) => L.labels[`${type}:${level}`])].join(', '))}</span>
    {open && <section className="wx-factors" id={`${id}-factors`} aria-label={L.more} data-layout-obstacle>
      <header><h2>{L.more}</h2><button type="button" className="wx-reset" disabled={busy} onClick={() => commit(MACRO_CLEAR)}>{L.reset}</button></header>
      {FACTORS.map((type, i) => <fieldset key={type} disabled={busy}>
        <legend>{L.groups[i]}</legend><div className="wx-pair">
          {macroOptions(tree, type).map((o) => <button key={o.level} type="button" aria-pressed={sel.factors[type] === o.level}
            onClick={() => commit(toggleFactor(sel, type, o.level))}>{L.labels[o.id] || o.label}</button>)}
        </div>
      </fieldset>)}
      <p>{L.note}</p>
    </section>}
  </aside>;
}
