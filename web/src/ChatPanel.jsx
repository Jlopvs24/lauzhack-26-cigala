import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { askLumi } from './conversation.js';
import { createHistory } from './chatHistory.js';
import { announcePanel, panelLayout } from './chatPanel.js';
import Dictation from './Dictation.jsx';
import { useVoiceNote } from './VoiceNote.jsx';
import { useLumiLive } from './live/LiveCall.jsx';
import { createGuide } from '../assets/character/guide/guide.js';
import '../assets/character/guide/guide.css';
import './chatPanel.css';

const TEXT = {
  en: { ask: 'Ask Lumi about this branch', send: 'Send', open: 'Open conversation', close: 'Close conversation',
    call: 'Call Lumi', title: 'Conversation with Lumi', empty: 'Ask anything about this branch: why it needs financing, what would have to be true, what changes if you wait a year.',
    you: 'You', lumi: 'Lumi', thinking: 'Lumi is checking the engine…', preparing: 'Preparing the voice note…', clear: 'Clear',
    sources: 'Calculation sources', template: 'Engine template', ai: 'AI explanation', node: 'node', replay: 'Read aloud',
    record: 'Record a voice note (sent when you stop)', stop: 'Stop and send', recording: 'Recording… press stop to send',
    noEngine: 'The engine is not reachable. Check that the API is running.' },
  es: { ask: 'Pregunta a Lumi sobre esta rama', send: 'Enviar', open: 'Abrir conversación', close: 'Cerrar conversación',
    call: 'Llamar a Lumi', title: 'Conversación con Lumi', empty: 'Pregunta lo que quieras sobre esta rama: por qué necesita financiación, qué tendría que cumplirse, qué cambia si esperas un año.',
    you: 'Tú', lumi: 'Lumi', thinking: 'Lumi está consultando el motor…', preparing: 'Preparando la nota de voz…', clear: 'Borrar',
    sources: 'Fuentes del cálculo', template: 'Plantilla del motor', ai: 'Explicación con IA', node: 'nodo', replay: 'Leer en voz alta',
    record: 'Grabar una nota de voz (se envía al parar)', stop: 'Parar y enviar', recording: 'Grabando… pulsa parar para enviar',
    noEngine: 'No se puede contactar con el motor. Comprueba que la API está en marcha.' },
  fr: { ask: 'Demande à Lumi à propos de cette branche', send: 'Envoyer', open: 'Ouvrir la conversation', close: 'Fermer la conversation',
    call: 'Appeler Lumi', title: 'Conversation avec Lumi', empty: 'Pose une question sur cette branche : pourquoi elle demande un financement, ce qui devrait être vrai, ce qui change si tu attends un an.',
    you: 'Toi', lumi: 'Lumi', thinking: 'Lumi consulte le moteur…', preparing: 'Préparation de la note vocale…', clear: 'Effacer',
    sources: 'Sources du calcul', template: 'Modèle du moteur', ai: 'Explication IA', node: 'nœud', replay: 'Lire à voix haute',
    record: 'Enregistrer une note vocale (envoyée à l’arrêt)', stop: 'Arrêter et envoyer', recording: 'Enregistrement… arrête pour envoyer',
    noEngine: 'Le moteur est injoignable. Vérifie que l’API tourne.' },
  de: { ask: 'Frag Lumi zu diesem Zweig', send: 'Senden', open: 'Gespräch öffnen', close: 'Gespräch schließen',
    call: 'Lumi anrufen', title: 'Gespräch mit Lumi', empty: 'Frag alles zu diesem Zweig: warum er eine Finanzierung braucht, was wahr sein müsste, was sich ändert, wenn du ein Jahr wartest.',
    you: 'Du', lumi: 'Lumi', thinking: 'Lumi prüft die Engine…', preparing: 'Sprachnachricht wird vorbereitet…', clear: 'Löschen',
    sources: 'Quellen der Berechnung', template: 'Engine-Vorlage', ai: 'KI-Erklärung', node: 'Knoten', replay: 'Vorlesen',
    record: 'Sprachnachricht aufnehmen (wird beim Stoppen gesendet)', stop: 'Stoppen und senden', recording: 'Aufnahme… stoppen zum Senden',
    noEngine: 'Die Engine ist nicht erreichbar. Läuft die API?' },
};

const Icon = ({ d, fill }) => <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
  {d.map((p, i) => <path key={i} d={p} fill={fill ? 'currentColor' : 'none'} stroke={fill ? 'none' : 'currentColor'} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />)}</svg>;
const MIC = ['M9 6a3 3 0 0 1 6 0v5a3 3 0 0 1-6 0z', 'M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21'];
const STOP = ['M8 8h8v8H8z'];
const PHONE = ['M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2'];
const CHAT = ['M4 5h16v11H9l-5 4z'];
const SEND = ['M5 12h13M13 6l6 6-6 6'];
const CLOSE = ['M6 6l12 12M18 6L6 18'];
const PLAY = ['M8 5l11 7-11 7z'];

// mouth: speaking on/off and, when the guide has it (thread 4), an opening level 0-1
function mouth(g, speaking, level) {
  if (speaking !== undefined) g.setTalking?.(!!speaking);
  if (Number.isFinite(level)) (g.setMouthLevel || g.setMouth || g.setLevel)?.call(g, Math.max(0, Math.min(1, level)));
}

const viewport = () => panelLayout(globalThis.innerWidth || 1280, globalThis.innerHeight || 800);

/**
 * Lumi's conversation (#34): a bottom-right dock when collapsed (send text, voice note sent when
 * recording stops, call Lumi, open the conversation) and a right side panel when open (bottom
 * sheet on phones). The panel announces the space it takes ('panel:open' / 'panel:close' and
 * --chat-panel-w/-h, see chatPanel.js) so the tree scene reflows instead of being covered.
 * The history is the whole session's (chatHistory.js): navigation never resets it.
 *
 * props: context (profile, path, node_id, assumptions, weather), lang, disabled, callUrl,
 * onAnswer(text, data) (the parent speaks it as Lumi unless muted), onCost(usd),
 * onOpenChange(open), onUnlock() (audio unlock on a user gesture), replay(text, lang),
 * history (optional store, for tests and demos).
 *
 * Docked Lumi (lead's layout): with `lumi`, Lumi lives at the bottom right just above the chat
 * line, with her bubble beside her; opening the conversation moves her into the panel header, so
 * Lumi + history + input are one panel and nothing floats over the tree.
 *   Events (main.jsx, #90): it announces itself with 'lumi:dock' {mounted} (the flying Lumi then steps
 *   aside), shows the narration from 'lumi:say' {text, lang, speaking} and moves the mouth with
 *   'lumi:level' {level 0-1}.
 *   Props (optional, override the events): say, sayNote (small node under the line), extra (node
 *   under the bubble), speaking, level; onGuide(guide) hands over the live Lumi (createGuide API).
 */
export default function ChatPanel({ context = {}, lang = 'en', disabled = false, callUrl, onAnswer, onCost,
  onOpenChange, onUnlock, replay, history: externalHistory,
  lumi = false, say = '', sayNote = null, extra = null, speaking, level, onGuide }) {
  const T = TEXT[lang] || TEXT.en;
  const history = useMemo(() => externalHistory || createHistory(), [externalHistory]);
  const [messages, setMessages] = useState(() => history.all());
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [pending, setPending] = useState(null); // the question on its way, shown until the answer lands
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [layout, setLayout] = useState(viewport);
  const request = useRef(null);
  const log = useRef(null);
  const field = useRef(null);
  const opener = useRef(null);
  const titleId = useId();
  const latest = useRef({});
  latest.current = { context, lang, onAnswer, onCost, onUnlock, onGuide };

  // docked Lumi: one live guide for the panel's whole life; it only changes place (CSS)
  const lumiEl = useRef(null), guide = useRef(null);
  const [heard, setHeard] = useState(''); // the narration from 'lumi:say'
  useEffect(() => {
    if (!lumi || !lumiEl.current) return undefined;
    const g = createGuide(lumiEl.current, { mood: 70, onTap: () => setOpen(true) });
    guide.current = g;
    latest.current.onGuide?.(g);
    const onLevel = (e) => mouth(g, e.detail?.speaking, e.detail?.level);
    const onSay = (e) => { setHeard(String(e.detail?.text || '')); if (e.detail?.speaking !== undefined) mouth(g, e.detail.speaking); };
    addEventListener('lumi:level', onLevel);
    addEventListener('lumi:say', onSay);
    dispatchEvent(new CustomEvent('lumi:dock', { detail: { mounted: true } }));
    return () => {
      removeEventListener('lumi:level', onLevel); removeEventListener('lumi:say', onSay);
      dispatchEvent(new CustomEvent('lumi:dock', { detail: { mounted: false } }));
      g.destroy?.(); guide.current = null;
    };
  }, [lumi]);
  const sayText = say || heard;
  useEffect(() => { if (guide.current && (speaking !== undefined || level !== undefined)) mouth(guide.current, speaking, level); }, [speaking, level]);

  useEffect(() => history.subscribe((list) => setMessages([...list])), [history]);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => { if (log.current) log.current.scrollTop = log.current.scrollHeight; }, [messages, open, busy, pending]);

  // tell the scene how much room the panel takes; again on resize while open
  useEffect(() => { announcePanel(open, layout); onOpenChange?.(open); },
    [open, layout.side, layout.width, layout.height]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const onResize = () => setLayout(viewport());
    addEventListener('resize', onResize);
    return () => { removeEventListener('resize', onResize); announcePanel(false, viewport()); };
  }, []);

  // focus into the field on open, back to the opener on close; Escape closes
  useEffect(() => {
    if (open) { field.current?.focus({ preventScroll: true }); return; }
    if (document.activeElement?.closest?.('.chatp-panel')) opener.current?.focus();
  }, [open]);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape' && !e.defaultPrevented) { e.preventDefault(); setOpen(false); } };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  async function send({ text, audio }) {
    const q = text?.trim();
    if (busy || disabled || (!audio && !q)) return;
    const { context: ctx, lang: l } = latest.current;
    latest.current.onUnlock?.();
    setBusy(true); setError('');
    const controller = new AbortController(); request.current = controller;
    if (q) { setPending(q); setQuestion(''); }
    try {
      const { user, assistant, cost } = await askLumi({ question: q, audio, context: { ...ctx, language: l },
        messages: history.forApi(), signal: controller.signal });
      latest.current.onCost?.(cost);
      const d = assistant.data || {};
      history.append('user', audio ? `🎙 ${user.content}` : user.content);
      history.append('assistant', assistant.content, {
        mode: d.mode, cost_usd: d.cost_usd, latency_ms: d.latency_ms, node_id: ctx.node_id,
        sources: (d.tool_traces || []).map((tr) => [tr.tool, tr.node_id && `${T.node} ${tr.node_id}`, tr.trace_id].filter(Boolean).join(' · ')),
      });
      latest.current.onAnswer?.(assistant.content, d);
    } catch (e) {
      if (controller.signal.aborted) return;
      if (q) setQuestion((cur) => cur || q); // give the text back instead of losing it
      setError(e instanceof TypeError ? T.noEngine : e.message);
    } finally {
      if (request.current === controller) { setBusy(false); setPending(null); }
    }
  }
  const voice = useVoiceNote((audio) => send({ audio }));
  const voiceBtn = <button type="button" className={`chatp-btn ${voice.recording ? 'is-rec' : ''}`}
    disabled={!voice.supported || voice.preparing || busy || disabled} aria-pressed={voice.recording}
    aria-label={voice.recording ? T.stop : T.record} title={voice.recording ? T.stop : T.record}
    onClick={() => { latest.current.onUnlock?.(); voice.toggle(); }}><Icon d={voice.recording ? STOP : MIC} fill={voice.recording} /></button>;
  const live = useLumiLive({ context, lang, history, onUnlock }); // thread 11: realtime call, classic link as fallback
  const callBtn = live.available ? <button type="button" className={`chatp-btn ${live.active ? 'is-rec' : ''}`} onClick={live.start} aria-label={T.call} title={T.call}><Icon d={PHONE} /></button>
    : callUrl && <a className="chatp-btn" href={callUrl} target="_blank" rel="noreferrer" aria-label={T.call} title={T.call}><Icon d={PHONE} /></a>;
  const status = voice.preparing ? T.preparing : busy ? T.thinking : '';
  const problem = error || voice.error;
  const turns = Math.ceil(messages.length / 2);
  const lastLumi = [...messages].reverse().find((m) => m.role === 'assistant')?.content;
  const line = sayText && sayText !== lastLumi ? sayText : ''; // in the open panel: the narration, unless it is the last answer

  return <div className={`chatp ${open ? 'is-open' : ''} ${lumi ? 'has-lumi' : ''}`} data-side={layout.side}
    style={{ '--chatp-w': `${layout.width}px`, '--chatp-h': `${layout.height}px` }}>
    {live.view}
    {lumi && <div className="chatp-lumi-host" data-layout-obstacle=""><div className="chatp-lumi" ref={lumiEl} /></div>}
    {!open && <div className="chatp-dock-wrap">
      {lumi && (sayText || extra) && <div className="chatp-say-col">
        {sayText && <div className="chatp-say" aria-live="polite"><p>{sayText}</p>{sayNote}</div>}
        {extra && <div className="chatp-extra">{extra}</div>}
      </div>}
      {(status || problem) && <p className={`chatp-bubble ${problem ? 'is-error' : ''}`} role={problem ? 'alert' : 'status'}>{problem || status}</p>}
      <form className="chatp-dock" autoComplete="off" onSubmit={(e) => { e.preventDefault(); send({ text: question }); }}>
        <input ref={field} className="chatp-dock-input" value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder={voice.recording ? T.recording : T.ask} aria-label={T.ask} disabled={disabled || voice.recording} maxLength={2000} />
        {voiceBtn}
        {callBtn}
        <button type="button" ref={opener} className="chatp-btn" onClick={() => setOpen(true)} aria-expanded="false" aria-label={T.open} title={T.open}>
          <Icon d={CHAT} />{turns > 0 && <span className="chatp-count" aria-hidden="true">{turns}</span>}</button>
        <button type="submit" className="chatp-btn chatp-send" disabled={disabled || busy || !question.trim()} aria-label={T.send} title={T.send}><Icon d={SEND} /></button>
      </form>
    </div>}

    {/* kept mounted so it can slide out; inert and hidden while closed */}
    <aside className="chatp-panel" aria-labelledby={titleId} aria-hidden={!open} inert={!open}>
      <header className="chatp-head">
        <h2 id={titleId}>{T.title}</h2>
        <div className="chatp-head-actions">
          {messages.length > 0 && <button type="button" className="chatp-link" onClick={() => history.clear()}>{T.clear}</button>}
          <button type="button" className="chatp-btn" onClick={() => setOpen(false)} aria-label={T.close} title={T.close}><Icon d={CLOSE} /></button>
        </div>
      </header>
      {lumi && (line || extra) && <div className="chatp-now">
        {line && <p className="chatp-now-line">{line}</p>}
        {extra && open && <div className="chatp-extra">{extra}</div>}
      </div>}
      <div className="chatp-log" ref={log} role="log" aria-live="polite" aria-label={T.title}>
        {messages.length === 0 && !pending && <p className="chatp-empty">{T.empty}</p>}
        {messages.map((m, i) => <article key={`${m.at}-${i}`} className={`chatp-msg ${m.role}`}>
          <strong>{m.role === 'user' ? T.you : T.lumi}</strong>
          <p>{m.content}</p>
          {m.meta && <footer>
            <small>{m.meta.mode === 'template' ? T.template : T.ai}{m.meta.node_id && ` · ${T.node} ${m.meta.node_id}`}{m.meta.latency_ms != null && ` · ${m.meta.latency_ms} ms`}</small>
            {m.meta.sources?.length > 0 && <details><summary>{T.sources}</summary><ul>{m.meta.sources.map((s, j) => <li key={j}>{s}</li>)}</ul></details>}
            {replay && <button type="button" className="chatp-link" onClick={() => replay(m.content, lang)} aria-label={T.replay} title={T.replay}><Icon d={PLAY} fill /></button>}
          </footer>}
        </article>)}
        {pending && <article className="chatp-msg user is-pending"><strong>{T.you}</strong><p>{pending}</p></article>}
        {status && <p className="chatp-thinking" role="status">{status}</p>}
      </div>
      {problem && <p className="chatp-error" role="alert">{problem}</p>}
      <form className="chatp-compose" autoComplete="off" onSubmit={(e) => { e.preventDefault(); send({ text: question }); }}>
        <textarea ref={open ? field : undefined} rows="2" value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder={voice.recording ? T.recording : T.ask} aria-label={T.ask} disabled={disabled || voice.recording} maxLength={2000}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send({ text: question }); } }} />
        <div className="chatp-compose-actions">
          <Dictation disabled={disabled || busy} onText={(w) => setQuestion((prev) => `${prev} ${w}`.trim())} />
          {voiceBtn}
          {callBtn}
          <button type="submit" className="chatp-btn chatp-send" disabled={disabled || busy || !question.trim()} aria-label={T.send} title={T.send}><Icon d={SEND} /></button>
        </div>
      </form>
    </aside>
  </div>;
}
