// Lumi's voice. The voice always matches the language: server Kokoro (/voice/tts) only for the
// languages /health lists, else a browser voice whose lang matches, else silence (never English
// text read by a Spanish voice, or the reverse). Audio unlocks on the first user gesture.
import { SPEECH_LANG } from './i18n.js';

const API = (import.meta.env?.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

export function createVoice({ onTalking = () => {}, onNoVoice = () => {} } = {}) {
  let unlocked = false, muted = false, audio = null, seq = 0, serverLangs = [];
  const cache = new Map(); // `${lang}|${text}` -> object URL: the same sentence is synthesised once
  fetch(`${API}/health`).then((r) => r.json())
    .then((h) => { if (h.voice?.kokoro?.available) serverLangs = h.voice.kokoro.languages || []; })
    .catch(() => {});

  function stop() {
    seq++;
    if (audio) { audio.pause(); audio = null; }
    try { speechSynthesis.cancel(); } catch { /* not supported */ }
    onTalking(false);
  }
  function browserVoice(lang) {
    if (!('speechSynthesis' in window)) return null;
    const vs = speechSynthesis.getVoices(), want = SPEECH_LANG[lang].toLowerCase();
    return vs.find((v) => v.lang.toLowerCase() === want) || vs.find((v) => v.lang.toLowerCase().startsWith(lang)) || null;
  }
  // Server voice, streamed: /voice/tts/stream sends one WAV per sentence (NDJSON), so Lumi starts
  // after the first sentence instead of waiting for the whole paragraph (a long French narration
  // took longer than any sane timeout as one file). Falls back to /voice/tts, then the browser.
  const b64url = (b64, type) => { const bin = atob(b64), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return URL.createObjectURL(new Blob([u], { type: type || 'audio/wav' })); };
  function playUrl(url, my) {
    return new Promise((resolve, reject) => {
      if (my !== seq) return resolve();
      audio = new Audio(url);
      audio.onplay = () => onTalking(true);
      audio.onended = () => resolve();
      audio.onpause = () => { onTalking(false); resolve(); };
      audio.onerror = () => reject(new Error('audio'));
      audio.play().catch(reject);
    });
  }
  async function* streamUrls(text, lang, my) {
    const r = await fetch(`${API}/voice/tts/stream`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language: lang }), signal: AbortSignal.timeout(60000) });
    if (!r.ok || !r.body) throw new Error(`tts stream ${r.status}`);
    const rd = r.body.getReader(), dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await rd.read();
      if (my !== seq) { rd.cancel().catch(() => {}); return; }
      buf += done ? '' : dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
        if (!line) continue;
        const d = JSON.parse(line);
        if (d.error) throw new Error(d.error);
        if (d.audio_b64) yield b64url(d.audio_b64, d.media_type);
      }
      if (done) return;
    }
  }
  async function serverSpeak(text, lang, my) {
    const key = `${lang}|${text}`;
    let urls = cache.get(key);
    if (urls) { for (const u of urls) { if (my !== seq) return; await playUrl(u, my); } return; }
    urls = [];
    let started = false, complete = false;
    try {
      // fetch sentence k+1 while sentence k plays
      const it = streamUrls(text, lang, my);
      let next = it.next();
      for (;;) {
        const { value, done } = await next;
        if (done) { complete = true; break; }
        if (my !== seq) break;
        urls.push(value); started = true;
        next = it.next(); next.catch(() => {});
        await playUrl(value, my);
      }
    } catch (e) {
      if (started || my !== seq) return; // mid-paragraph failure: stop quietly rather than restart
      const r = await fetch(`${API}/voice/tts`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, language: lang }), signal: AbortSignal.timeout(30000) });
      if (!r.ok) throw new Error(`tts ${r.status}`);
      const u = URL.createObjectURL(await r.blob());
      urls = [u]; complete = true;
      if (my === seq) await playUrl(u, my);
    }
    if (complete && urls.length) {
      if (cache.size > 40) { const [k, us] = cache.entries().next().value; us.forEach((u) => URL.revokeObjectURL(u)); cache.delete(k); }
      cache.set(key, urls);
    }
    if (my === seq) onTalking(false);
  }
  async function speak(text, lang) {
    stop();
    if (muted || !unlocked || !text) return;
    const my = seq;
    try {
      if (!serverLangs.includes(lang)) throw new Error(`no server voice for ${lang}`);
      await serverSpeak(text, lang, my);
    } catch {
      if (my !== seq) return;
      const v = browserVoice(lang);
      if (!v) { onNoVoice(lang); return; }
      const u = new SpeechSynthesisUtterance(text);
      u.voice = v; u.lang = v.lang; u.rate = 1.02;
      u.onstart = () => onTalking(true);
      u.onend = u.onerror = () => onTalking(false);
      speechSynthesis.speak(u);
    }
  }
  return {
    unlock() {
      if (unlocked) return;
      unlocked = true;
      try { const a = new Audio(); a.muted = true; a.play().catch(() => {}); } catch { /* ignore */ }
      try { speechSynthesis.speak(new SpeechSynthesisUtterance('')); } catch { /* ignore */ }
    },
    speak, stop,
    setMuted(m) { muted = m; if (m) stop(); },
    get muted() { return muted; },
  };
}
