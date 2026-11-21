import React, { useEffect, useRef, useState } from 'react';
import { askLumi } from './conversation.js';
import { useVoiceNote } from './VoiceNote.jsx';

const Icon = ({ d, fill }) => <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
  {d.map((p, i) => <path key={i} d={p} fill={fill ? 'currentColor' : 'none'} stroke={fill ? 'none' : 'currentColor'} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />)}</svg>;
const MIC = ['M9 6a3 3 0 0 1 6 0v5a3 3 0 0 1-6 0z', 'M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21'];
const STOP = ['M8 8h8v8H8z'];
const PHONE = ['M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2']; // eslint-disable-line
const CHAT = ['M4 5h16v11H9l-5 4z'];
const SEND = ['M5 12h13M13 6l6 6-6 6'];

// The bottom-right dock: send text, send a voice note (auto-sent when recording stops),
// call Lumi, and open the conversation (the whole session's history, both sides).
export default function Dock({ t, lang, context, messages, setMessages, open, setOpen, disabled, onAnswer, onCost, callUrl, onUnlock }) {
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const log = useRef(null);
  const request = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => { if (open && log.current) log.current.scrollTop = log.current.scrollHeight; }, [messages, open, busy]);

  async function send({ text, audio }) {
    if (busy || disabled || (!audio && !text?.trim())) return;
    onUnlock?.();
    setBusy(true); setError('');
    const controller = new AbortController(); request.current = controller;
    if (text) { setQuestion(''); setMessages((m) => [...m, { role: 'user', content: text.trim(), pending: true }]); }
    try {
      const prior = messages.filter((m) => !m.pending);
      const { user, assistant, cost } = await askLumi({ question: text, audio, context: { ...context, language: lang }, messages: prior, signal: controller.signal });
      onCost?.(cost);
      setMessages((m) => [...m.filter((x) => !x.pending), user, assistant]); // history always kept
      onAnswer?.(assistant.content);
    } catch (e) {
      if (controller.signal.aborted) return;
      setMessages((m) => m.map((x) => (x.pending ? { ...x, pending: false, failed: true } : x)));
      setError(e instanceof TypeError ? t('noEngine') : e.message);
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }
  const voice = useVoiceNote((audio) => send({ audio }));

  return <div className={`dock ${open ? 'open' : ''}`}>
    {open && <section className="conv" aria-label={t('conversation')}>
      <header><span>{t('conversation')}</span>
        <button type="button" className="conv-close" onClick={() => setOpen(false)} aria-label={t('closeConv')}>×</button></header>
      <div className="conv-log" ref={log} role="log" aria-live="polite">
        {!messages.length && <p className="conv-empty">{t('convEmpty')}</p>}
        {messages.map((m, i) => <article key={i} className={`msg ${m.role} ${m.failed ? 'failed' : ''}`}>
          <strong>{m.role === 'user' ? (m.voice ? `${t('you')} · 🎙` : t('you')) : 'Lumi'}</strong>
          <p>{m.content}</p>
          {m.data && <details><summary>{t('sources')}</summary>
            <small>{m.data.mode === 'template' ? 'Engine template' : 'AI explanation'} · USD {Number(m.data.cost_usd || 0).toFixed(5)} · {m.data.latency_ms} ms</small>
            <ul>{(m.data.tool_traces || []).map((tr, j) => <li key={j}>{tr.tool}{tr.node_id && ` · node ${tr.node_id}`}{tr.trace_id && ` · ${tr.trace_id}`}</li>)}</ul></details>}
        </article>)}
        {(busy || voice.preparing) && <p className="conv-typing">{voice.preparing ? t('preparing') : t('thinking')}</p>}
      </div>
    </section>}
    {(error || voice.error) && <p className="dock-error" role="alert">{error || voice.error}</p>}
    <form className="ask" autoComplete="off" onSubmit={(e) => { e.preventDefault(); send({ text: question }); }}>
      <input value={question} onChange={(e) => setQuestion(e.target.value)} disabled={voice.recording}
        placeholder={voice.recording ? t('recording') : t('ask')} aria-label={t('ask')} />
      <button type="button" className={`icon-btn ${voice.recording ? 'rec' : ''}`} disabled={!voice.supported || voice.preparing || busy || disabled}
        aria-pressed={voice.recording} aria-label={voice.recording ? t('stopRec') : t('record')} title={voice.recording ? t('stopRec') : t('record')}
        onClick={() => { onUnlock?.(); voice.toggle(); }}><Icon d={voice.recording ? STOP : MIC} fill={voice.recording} /></button>
      <a className="icon-btn" href={callUrl} target="_blank" rel="noreferrer" aria-label={t('call')} title={t('call')}><Icon d={PHONE} /></a>
      <button type="button" className={`icon-btn ${open ? 'on' : ''}`} aria-pressed={open} aria-label={open ? t('closeConv') : t('openConv')} title={open ? t('closeConv') : t('openConv')}
        onClick={() => setOpen(!open)}><Icon d={CHAT} />{!open && messages.length > 0 && <span className="badge">{Math.ceil(messages.length / 2)}</span>}</button>
      <button type="submit" className="icon-btn send" aria-label={t('send')} disabled={busy || !question.trim()}><Icon d={SEND} /></button>
    </form>
  </div>;
}
