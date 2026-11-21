// Weather on the tree (#65): toggle chips (from tree.weather_options) + a "when" slider and a
// duration. The parent re-requests /tree/expand with `weather` so every visible card recomputes.
import React, { useEffect, useId, useRef, useState } from 'react';
import { W_I18N } from './weatherI18n.js';
import { CLEAR, DURATION_MAX, START_MAX, WITH_DURATION, buildWeather, stormLine, stormSummary, toggle, weatherOptions } from './weatherModel.js';
import './weather.css';

const ICON = {
  recession: 'M4 15a4 4 0 0 1 1-7.9A6 6 0 0 1 16.6 8 3.5 3.5 0 0 1 17 15H4Zm3 2-1 3m5-3-1 3m5-3-1 3',
  inflation: 'M12 3c3 4 5 6 5 9a5 5 0 0 1-10 0c0-2 1-3.5 2-4.5.3 1.5 1 2.5 2 3 0-3 0-5 1-7.5Z',
  market_crash: 'M3 5l6 6 4-4 8 8m0 0v-5m0 5h-5',
  job_loss: 'M8 7V5h8v2m-12 0h16v12H4V7Zm5 5h6',
  chf_strengthens: 'M12 19V5m0 0-5 5m5-5 5 5',
  chf_weakens: 'M12 5v14m0 0-5-5m5 5 5-5',
};

export default function WeatherControl({ lang = 'en', tree, busy = false, onChange }) {
  const L = W_I18N[lang] || W_I18N.en;
  const [sel, setSel] = useState(CLEAR);
  const applied = useRef(JSON.stringify([]));
  const timer = useRef(null);
  const ids = useId();
  const opts = weatherOptions(tree, lang);

  // commit after a short pause so a slider drag sends one request, not twenty
  function commit(next, delay = 0) {
    setSel(next);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const w = buildWeather(next);
      const key = JSON.stringify(w);
      if (key === applied.current) return;
      applied.current = key;
      onChange?.(w);
    }, delay);
  }
  useEffect(() => () => clearTimeout(timer.current), []);

  if (!opts.length) return null;
  const weather = buildWeather(sel);
  const showDuration = sel.types.some((t) => WITH_DURATION.has(t));
  const line = busy && weather.length ? L.recomputing : stormLine(lang, tree?.weather?.length ? tree.weather : [], stormSummary(tree));

  return <section className={`wx ${weather.length ? 'wx-on' : ''}`} aria-labelledby={`${ids}-t`}>
    <div className="wx-head">
      <h2 className="wx-title" id={`${ids}-t`}>{L.title}</h2>
      <button type="button" className="wx-clear" aria-pressed={!weather.length} onClick={() => commit(CLEAR)}>{L.clear}</button>
    </div>
    <div className="wx-chips" role="group" aria-label={L.group}>
      {opts.map((o) => {
        const on = sel.types.includes(o.type);
        return <button key={o.type} type="button" className="wx-chip" aria-pressed={on} title={o.description}
          aria-describedby={`${ids}-${o.type}`} onClick={() => commit(toggle(sel, o.type))}>
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d={ICON[o.type] || 'M12 4v16M4 12h16'} /></svg>
          <span>{o.label}</span>
          <span className="sr-only" id={`${ids}-${o.type}`}>{o.description}</span>
        </button>;
      })}
    </div>
    {weather.length > 0 && <div className="wx-sliders">
      <label className="wx-range">
        <span>{L.when(sel.start + 1)}</span>
        <input type="range" min="0" max={START_MAX} step="1" value={sel.start}
          aria-valuetext={L.when(sel.start + 1)} onChange={(e) => commit({ ...sel, start: Number(e.target.value) }, 400)} />
      </label>
      {showDuration && <label className="wx-range">
        <span>{sel.duration == null ? L.defaultLasts : L.lasts(sel.duration)}</span>
        <input type="range" min="1" max={DURATION_MAX} step="1" value={sel.duration ?? 18}
          aria-valuetext={sel.duration == null ? L.defaultLasts : L.lasts(sel.duration)}
          onChange={(e) => commit({ ...sel, duration: Number(e.target.value) }, 400)} />
      </label>}
    </div>}
    {line && <p className="wx-line" role="status" aria-live="polite">{line}</p>}
  </section>;
}
