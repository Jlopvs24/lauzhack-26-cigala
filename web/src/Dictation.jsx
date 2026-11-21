import React, { useEffect, useRef, useState } from 'react';

export default function Dictation({ disabled, onText }) {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState('');
  const [language, setLanguage] = useState('en-US');
  const recognition = useRef(null);
  const callback = useRef(onText);
  callback.current = onText;
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  useEffect(() => () => recognition.current?.abort(), []);
  useEffect(() => { if (disabled) recognition.current?.stop(); }, [disabled]);

  function toggle() {
    if (listening) { recognition.current?.stop(); return; }
    setError('');
    const session = new Recognition();
    session.lang = language;
    session.interimResults = false;
    session.continuous = false;
    session.onresult = event => {
      const text = Array.from(event.results).slice(event.resultIndex).map(result => result[0].transcript).join(' ');
      if (text) callback.current(text);
    };
    session.onerror = event => setError(`Dictation ${event.error}. You can type or upload an audio file instead.`);
    session.onend = () => setListening(false);
    recognition.current = session;
    try { session.start(); setListening(true); }
    catch { setError('Could not start dictation. Please type instead.'); }
  }
  return <div className="dictation"><div className="dictation-controls"><select aria-label="Dictation language" value={language} disabled={disabled || listening} onChange={event => setLanguage(event.target.value)}>
    <option value="en-US">English</option><option value="es-ES">Spanish</option><option value="fr-FR">French</option><option value="de-DE">German</option>
  </select><button type="button" className="back" disabled={disabled || !Recognition} aria-pressed={listening} onClick={toggle}>{listening ? 'Stop dictation' : 'Dictate'}</button></div>
    <small>{Recognition ? 'Optional browser dictation may send audio to your browser provider. Review the text before sending.' : 'Browser dictation is unavailable. Type or upload an audio file.'}</small>
    {error && <p role="alert" className="negative">{error}</p>}
  </div>;
}
