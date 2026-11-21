import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { apiRequest } from './api.js';

// "Verified": the engine's live checks (GET /validation -> core.validation()). A small badge in the
// header opens a panel with one row per check: pass/fail, detail, evidence behind a disclosure.
// Other views (e.g. the path report) can open it with window.dispatchEvent(new Event('verified:open')).
const T = {
  en: { badge: (p, n) => `Verified ${p}/${n}`, title: 'Verified by the engine, live', lede: 'These checks run on the engine now, on the whole tree. They test the arithmetic and the method, not the future.', evidence: 'Evidence', pass: 'passed', fail: 'failed', close: 'Close', ms: (ms) => `ran in ${ms} ms`, unavailable: 'The validation service is not available right now.' },
  es: { badge: (p, n) => `Verificado ${p}/${n}`, title: 'Verificado por el motor, en directo', lede: 'Estos controles se ejecutan ahora sobre todo el árbol. Prueban la aritmética y el método, no el futuro.', evidence: 'Evidencia', pass: 'superado', fail: 'fallido', close: 'Cerrar', ms: (ms) => `en ${ms} ms`, unavailable: 'El servicio de validación no está disponible ahora.' },
  fr: { badge: (p, n) => `Vérifié ${p}/${n}`, title: 'Vérifié par le moteur, en direct', lede: 'Ces contrôles tournent maintenant sur tout l’arbre. Ils testent l’arithmétique et la méthode, pas l’avenir.', evidence: 'Preuves', pass: 'réussi', fail: 'échoué', close: 'Fermer', ms: (ms) => `en ${ms} ms`, unavailable: 'Le service de validation n’est pas disponible pour le moment.' },
  de: { badge: (p, n) => `Geprüft ${p}/${n}`, title: 'Live von der Engine geprüft', lede: 'Diese Prüfungen laufen jetzt auf dem ganzen Baum. Sie testen die Rechnung und die Methode, nicht die Zukunft.', evidence: 'Belege', pass: 'bestanden', fail: 'nicht bestanden', close: 'Schließen', ms: (ms) => `in ${ms} ms`, unavailable: 'Der Prüfdienst ist gerade nicht verfügbar.' },
};

export function useValidation() {
  const [data, setData] = useState(null);
  useEffect(() => {
    let live = true, timer;
    const load = () => apiRequest('/validation', { method: 'GET' })
      .then((d) => { if (live && Array.isArray(d?.checks)) setData(d); })
      .catch(() => { if (live) timer = setTimeout(load, 60000); }); // service not deployed yet: retry quietly
    load();
    return () => { live = false; clearTimeout(timer); };
  }, []);
  return data;
}

export default function Verified({ lang = 'en' }) {
  const L = T[lang] || T.en;
  const data = useValidation();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const o = () => setOpen(true);
    const k = (e) => e.key === 'Escape' && setOpen(false);
    addEventListener('verified:open', o); addEventListener('keydown', k);
    return () => { removeEventListener('verified:open', o); removeEventListener('keydown', k); };
  }, []);
  if (!data) return null;
  const passed = data.passed ?? data.checks.filter((c) => c.passed).length, total = data.total ?? data.checks.length;
  const ok = passed === total;
  return <>
    <button type="button" className={`verified-badge ${ok ? 'ok' : 'bad'}`} onClick={() => setOpen(true)} aria-haspopup="dialog">
      <span aria-hidden="true">{ok ? '✓' : '!'}</span><em>{L.badge(passed, total)}</em><i>{passed}/{total}</i></button>
    {open && createPortal(<div className="verified-scrim" onClick={(e) => e.target === e.currentTarget && setOpen(false)}>
      <section className="verified-panel" role="dialog" aria-modal="true" aria-labelledby="verified-title">
        <button className="close" onClick={() => setOpen(false)} aria-label={L.close}>×</button>
        <p className="verified-kicker">{data.engine_version} · {L.ms(data.duration_ms ?? '–')}</p>
        <h2 id="verified-title">{L.title}</h2>
        <p className="verified-lede">{L.lede}</p>
        <ul className="verified-list">{data.checks.map((c) => <li key={c.id} className={c.passed ? 'ok' : 'bad'}>
          <span className="pf" aria-label={c.passed ? L.pass : L.fail}>{c.passed ? '✓' : '✕'}</span>
          <div><b>{c.label || c.id}</b>{c.detail && <p>{c.detail}</p>}
            {c.evidence != null && <details><summary>{L.evidence}</summary>
              <pre>{typeof c.evidence === 'string' ? c.evidence : JSON.stringify(c.evidence, null, 2)}</pre></details>}</div>
        </li>)}</ul>
        {data.how && <p className="verified-how">{data.how}</p>}
      </section>
    </div>, document.body)}
  </>;
}
