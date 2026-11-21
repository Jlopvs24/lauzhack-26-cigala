import React, { useEffect, useRef, useState } from 'react';
import { apiRequest } from './api.js';
import Dictation from './Dictation.jsx';
import VoiceNote from './VoiceNote.jsx';

export default function Chat({ context, disabled, onCost }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [speaking, setSpeaking] = useState(false);
  const [autoRead, setAutoRead] = useState(true);
  const request = useRef(null);
  const log = useRef(null);
  const canSpeak = 'speechSynthesis' in window;
  useEffect(() => () => { request.current?.abort(); window.speechSynthesis?.cancel(); }, []);
  useEffect(() => { if (log.current) log.current.scrollTop = log.current.scrollHeight; }, [messages]);

  async function ask(event, audio) {
    event?.preventDefault();
    if (busy || disabled || (!audio && !question.trim())) return;
    if (audio && (!/\.(wav|mp3)$/i.test(audio.name) || audio.size > 10 * 1024 * 1024)) {
      setError('Choose a WAV or MP3 voice note, no larger than 10 MB.'); return;
    }
    setBusy(true); setError('');
    const controller = new AbortController(); request.current = controller;
    const history = messages.slice(-10).map(({ role, content }) => ({ role, content }));
    let body = { question: question.trim(), context: { ...context, history } };
    if (audio) {
      body = new FormData(); body.append('audio', audio); body.append('context', JSON.stringify({ ...context, history }));
    }
    try {
      const data = await apiRequest(audio ? '/voice/ask' : '/agent/ask', { body, signal: controller.signal });
      onCost(data.cost_usd);
      if (typeof data.answer !== 'string' || data.grounding?.grounded === false) throw new Error('The answer could not be verified against the calculation engine. Please try again.');
      setMessages(previous => [...previous, { role: 'user', content: audio ? data.transcript || 'Voice note' : question.trim() },
        { role: 'assistant', content: data.answer, data }]);
      setQuestion('');
      if (autoRead && canSpeak) read({ content: data.answer, data });
    } catch (failure) { if (!controller.signal.aborted) setError(failure.message); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  function read(message) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(message.content);
    utterance.lang = { es: 'es-ES', fr: 'fr-FR', de: 'de-DE' }[message.data.language] || 'en-US';
    utterance.onend = utterance.onerror = () => setSpeaking(false);
    setSpeaking(true); window.speechSynthesis.speak(utterance);
  }
  return <section className="chat-panel" aria-labelledby="chat-heading"><div className="chat-heading"><span aria-hidden="true">✳</span><div>
    <p className="eyebrow">YOUR BRANCH, EXPLAINED</p><h2 id="chat-heading">Ask your guide</h2></div></div>
    <p>Ask about this branch and its trade-offs. Answers use the calculation engine. Changing the branch or assumptions starts a fresh conversation.</p>
    <label className="read-toggle"><input type="checkbox" checked={autoRead} disabled={!canSpeak} onChange={event => { setAutoRead(event.target.checked); if (!event.target.checked) { window.speechSynthesis?.cancel(); setSpeaking(false); } }} />Read new replies aloud</label>
    <div className="chat-messages" ref={log} role="log" aria-label="Conversation" aria-live="polite">{messages.map((message, i) => <article key={i} className={`chat-message ${message.role}`}>
      <strong>{message.role === 'user' ? 'You' : 'Your guide'}</strong><p>{message.content}</p>
      {message.data && <><small>{message.data.mode === 'template' ? 'Engine template' : 'AI explanation'} · USD {Number(message.data.cost_usd || 0).toFixed(5)} · {message.data.latency_ms} ms</small>
        <details><summary>Calculation sources</summary><ul>{(message.data.tool_traces || []).map((trace, j) => <li key={j}>{trace.tool}{trace.trace_id && ` · ${trace.trace_id}`}{trace.node_id && ` · node ${trace.node_id}`}</li>)}</ul></details>
        <button type="button" className="back" disabled={!canSpeak} onClick={() => read(message)}>Read aloud</button></>}
    </article>)}</div>
    {speaking && <button type="button" className="back" onClick={() => { window.speechSynthesis.cancel(); setSpeaking(false); }}>Stop reading</button>}
    <form onSubmit={ask}><fieldset disabled={busy || disabled}><legend className="sr-only">Ask about this scenario</legend>
      <label>Your question<textarea value={question} onChange={event => setQuestion(event.target.value)} rows="3" placeholder="Why does this path need extra financing?" /></label>
      <Dictation disabled={busy || disabled} onText={words => setQuestion(previous => `${previous} ${words}`.trim())} />
      <div className="form-actions"><button className="primary" type="submit" disabled={!question.trim()}>Send question</button>
        <VoiceNote disabled={busy || disabled} onSend={audio => ask(null, audio)} />
        <label className="audio-upload">Or send a voice note (WAV/MP3)<input type="file" accept=".wav,.mp3,audio/wav,audio/mpeg" onChange={event => { const file = event.target.files[0]; event.target.value = ''; if (file) ask(null, file); }} /></label></div>
    </fieldset></form>
    {busy && <p role="status">Checking the scenario and preparing an explanation…</p>}{error && <p role="alert" className="negative">{error}</p>}
  </section>;
}
