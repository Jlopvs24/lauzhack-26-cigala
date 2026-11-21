import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { apiRequest } from './api.js';
import { createHistory } from './chatHistory.js';
import { announcePanel, panelLayout } from './chatPanel.js';
import Dictation from './Dictation.jsx';
import VoiceNote from './VoiceNote.jsx';
import './chatPanel.css';

const TEXT = {
  en: { ask: 'Ask Lumi about this branch', send: 'Send', open: 'Open conversation', close: 'Close conversation',
    call: 'Call Lumi', title: 'Conversation with Lumi', empty: 'Ask anything about this branch: why it needs financing, what would have to be true, what changes if you wait a year.',
    you: 'You', lumi: 'Lumi', thinking: 'Lumi is checking the engine…', clear: 'Clear', sources: 'Calculation sources',
    template: 'Engine template', ai: 'AI explanation', unverified: 'The answer could not be verified against the engine. Please try again.',
    badAudio: 'Choose a WAV or MP3 voice note, no larger than 10 MB.', node: 'node' },
  es: { ask: 'Pregunta a Lumi sobre esta rama', send: 'Enviar', open: 'Abrir conversación', close: 'Cerrar conversación',
    call: 'Llamar a Lumi', title: 'Conversación con Lumi', empty: 'Pregunta lo que quieras sobre esta rama: por qué necesita financiación, qué tendría que cumplirse, qué cambia si esperas un año.',
    you: 'Tú', lumi: 'Lumi', thinking: 'Lumi está consultando el motor…', clear: 'Borrar', sources: 'Fuentes del cálculo',
    template: 'Plantilla del motor', ai: 'Explicación con IA', unverified: 'No se pudo verificar la respuesta con el motor. Inténtalo de nuevo.',
    badAudio: 'Elige una nota de voz WAV o MP3 de 10 MB como máximo.', node: 'nodo' },
  fr: { ask: 'Demande à Lumi à propos de cette branche', send: 'Envoyer', open: 'Ouvrir la conversation', close: 'Fermer la conversation',
    call: 'Appeler Lumi', title: 'Conversation avec Lumi', empty: 'Pose une question sur cette branche : pourquoi elle demande un financement, ce qui devrait être vrai, ce qui change si tu attends un an.',
    you: 'Toi', lumi: 'Lumi', thinking: 'Lumi consulte le moteur…', clear: 'Effacer', sources: 'Sources du calcul',
    template: 'Modèle du moteur', ai: 'Explication IA', unverified: "La réponse n'a pas pu être vérifiée par le moteur. Réessaie.",
    badAudio: 'Choisis une note vocale WAV ou MP3 de 10 Mo maximum.', node: 'nœud' },
  de: { ask: 'Frag Lumi zu diesem Zweig', send: 'Senden', open: 'Gespräch öffnen', close: 'Gespräch schließen',
    call: 'Lumi anrufen', title: 'Gespräch mit Lumi', empty: 'Frag alles zu diesem Zweig: warum er eine Finanzierung braucht, was wahr sein müsste, was sich ändert, wenn du ein Jahr wartest.',
    you: 'Du', lumi: 'Lumi', thinking: 'Lumi prüft die Engine…', clear: 'Löschen', sources: 'Quellen der Berechnung',
    template: 'Engine-Vorlage', ai: 'KI-Erklärung', unverified: 'Die Antwort konnte nicht mit der Engine geprüft werden. Bitte erneut versuchen.',
    badAudio: 'Wähle eine WAV- oder MP3-Sprachnachricht bis 10 MB.', node: 'Knoten' },
};

const viewport = () => panelLayout(globalThis.innerWidth || 1280, globalThis.innerHeight || 800);

/**
 * Lumi's conversation: a bottom-right dock when collapsed, a right side panel (bottom sheet
 * on phones) when open. The panel announces the space it takes ('panel:open' / 'panel:close'
 * + --chat-panel-w/-h, see chatPanel.js) so the tree scene reflows instead of being covered.
 *
 * props: context (sent to /agent/ask: profile, path, node_id, assumptions, weather, language),
 * lang, muted, speak(text) (Lumi's voice), onCost(usd), onAnswer(text, data), onOpenChange(open),
 * callUrl, disabled, history (optional store from createHistory, for tests and demos).
 */
export default function ChatPanel({ context = {}, lang = 'en', muted = false, speak, onCost, onAnswer,
  onOpenChange, callUrl, disabled = false, history: externalHistory }) {
  const T = TEXT[lang] || TEXT.en;
  const history = useMemo(() => externalHistory || createHistory(), [externalHistory]);
  const [messages, setMessages] = useState(() => history.all());
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [layout, setLayout] = useState(viewport);
  const request = useRef(null);
  const log = useRef(null);
  const input = useRef(null);
  const opener = useRef(null);
  const titleId = useId();
  const latest = useRef({ context, lang, muted, speak, onCost, onAnswer });
  latest.current = { context, lang, muted, speak, onCost, onAnswer };

  useEffect(() => history.subscribe((list) => setMessages([...list])), [history]);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => { if (log.current) log.current.scrollTop = log.current.scrollHeight; }, [messages, open, busy]);

  // tell the scene how much room the panel takes; again on resize while open
  useEffect(() => {
    announcePanel(open, layout);
    onOpenChange?.(open);
  }, [open, layout.side, layout.width, layout.height]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const onResize = () => setLayout(viewport());
    addEventListener('resize', onResize);
    return () => { removeEventListener('resize', onResize); announcePanel(false, viewport()); };
  }, []);

  // focus: into the input on open, back to the opener on close; Escape closes
  useEffect(() => {
    if (open) { input.current?.focus({ preventScroll: true }); return undefined; }
    if (document.activeElement && document.activeElement.closest?.('.chatp-panel')) opener.current?.focus();
    return undefined;
  }, [open]);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape' && !e.defaultPrevented) { e.preventDefault(); setOpen(false); } };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  async function ask(event, audio) {
    event?.preventDefault();
    const text = question.trim();
    if (busy || disabled || (!audio && !text)) return;
    if (audio && (!/\.(wav|mp3)$/i.test(audio.name) || audio.size > 10 * 1024 * 1024)) { setError(T.badAudio); return; }
    const { context: ctx, lang: l } = latest.current;
    setBusy(true); setError('');
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    const full = { ...ctx, language: ctx.language || l, history: history.forApi() };
    let body = { question: text, context: full };
    if (audio) { body = new FormData(); body.append('audio', audio); body.append('context', JSON.stringify(full)); }
    if (!audio) { history.append('user', text); setQuestion(''); }
    try {
      const data = await apiRequest(audio ? '/voice/ask' : '/agent/ask', { body, signal: controller.signal });
      latest.current.onCost?.(data.cost_usd);
      if (typeof data.answer !== 'string' || data.grounding?.grounded === false) throw new Error(T.unverified);
      if (audio) history.append('user', data.transcript || '🎙');
      history.append('assistant', data.answer, {
        mode: data.mode, cost_usd: data.cost_usd, latency_ms: data.latency_ms, node_id: ctx.node_id,
        sources: (data.tool_traces || []).map((t) => [t.tool, t.trace_id, t.node_id && `${T.node} ${t.node_id}`].filter(Boolean).join(' · ')),
      });
      latest.current.onAnswer?.(data.answer, data);
      if (!latest.current.muted) latest.current.speak?.(data.answer, data.language || l);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message);
    } finally { if (request.current === controller) setBusy(false); }
  }

  const onDictated = (words) => setQuestion((prev) => `${prev} ${words}`.trim());

  return <div className={`chatp ${open ? 'is-open' : ''}`} data-side={layout.side}
    style={{ '--chatp-w': `${layout.width}px`, '--chatp-h': `${layout.height}px` }}>
    {/* collapsed: the dock with four actions */}
    {!open && <form className="chatp-dock" onSubmit={ask} aria-label={T.ask}>
      <input ref={input} className="chatp-dock-input" value={question} onChange={(e) => setQuestion(e.target.value)}
        placeholder={T.ask} aria-label={T.ask} disabled={disabled || busy} maxLength={2000} />
      <button type="submit" className="chatp-btn chatp-send" disabled={disabled || busy || !question.trim()} aria-label={T.send}>↑</button>
      <div className="chatp-dock-voice"><VoiceNote disabled={disabled || busy} onSend={(f) => ask(null, f)} /></div>
      {callUrl && <a className="chatp-btn" href={callUrl} target="_blank" rel="noreferrer" aria-label={T.call} title={T.call}>☎</a>}
      <button type="button" ref={opener} className="chatp-btn chatp-open" onClick={() => setOpen(true)}
        aria-expanded="false" aria-label={T.open} title={T.open}>
        ☰{messages.length > 0 && <span className="chatp-count" aria-hidden="true">{Math.ceil(messages.length / 2)}</span>}
      </button>
      {busy && <span className="chatp-dock-status" role="status">{T.thinking}</span>}
    </form>}

    {/* expanded: side panel (bottom sheet on phones); kept mounted so it can slide out */}
    <aside className="chatp-panel" aria-labelledby={titleId} aria-hidden={!open} inert={!open}>
      <header className="chatp-head">
        <h2 id={titleId}>{T.title}</h2>
        <div className="chatp-head-actions">
          {messages.length > 0 && <button type="button" className="chatp-link" onClick={() => history.clear()}>{T.clear}</button>}
          <button type="button" className="chatp-btn" onClick={() => setOpen(false)} aria-label={T.close} title={T.close}>×</button>
        </div>
      </header>
      <div className="chatp-log" ref={log} role="log" aria-live="polite" aria-label={T.title}>
        {messages.length === 0 && <p className="chatp-empty">{T.empty}</p>}
        {messages.map((m, i) => <article key={`${m.at}-${i}`} className={`chatp-msg ${m.role}`}>
          <strong>{m.role === 'user' ? T.you : T.lumi}</strong>
          <p>{m.content}</p>
          {m.meta && <footer>
            <small>{m.meta.mode === 'template' ? T.template : T.ai}{m.meta.node_id && ` · ${T.node} ${m.meta.node_id}`}{m.meta.latency_ms != null && ` · ${m.meta.latency_ms} ms`}</small>
            {m.meta.sources?.length > 0 && <details><summary>{T.sources}</summary><ul>{m.meta.sources.map((s, j) => <li key={j}>{s}</li>)}</ul></details>}
            {speak && <button type="button" className="chatp-link" onClick={() => speak(m.content, lang)}>▶</button>}
          </footer>}
        </article>)}
        {busy && <p className="chatp-thinking" role="status">{T.thinking}</p>}
      </div>
      {error && <p className="chatp-error" role="alert">{error}</p>}
      <form className="chatp-compose" onSubmit={ask}>
        <textarea ref={open ? input : undefined} rows="2" value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder={T.ask} aria-label={T.ask} disabled={disabled || busy} maxLength={2000}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) ask(e); }} />
        <div className="chatp-compose-actions">
          <Dictation disabled={disabled || busy} onText={onDictated} />
          <VoiceNote disabled={disabled || busy} onSend={(f) => ask(null, f)} />
          {callUrl && <a className="chatp-btn" href={callUrl} target="_blank" rel="noreferrer" aria-label={T.call} title={T.call}>☎</a>}
          <button type="submit" className="chatp-btn chatp-send" disabled={disabled || busy || !question.trim()} aria-label={T.send}>↑</button>
        </div>
      </form>
    </aside>
  </div>;
}
