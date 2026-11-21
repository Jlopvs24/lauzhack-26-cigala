// Lumi's voice. The voice always matches the language: server Kokoro (/voice/tts) only for the
// languages /health lists, else a browser voice whose lang matches, else silence (never English
// text read by a Spanish voice, or the reverse). Audio unlocks on the first user gesture.
import { SPEECH_LANG } from './i18n.js';

const API = (import.meta.env?.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

export function createVoice({ onTalking = () => {}, onNoVoice = () => {} } = {}) {
  let unlocked = false, muted = false, audio = null, seq = 0, serverLangs = [], disposed = false;
  const inflight = new Set(); // AbortControllers of /voice/tts(/stream) requests: stop() aborts them all
  function request(path, text, lang, ms) {
    const c = new AbortController(); inflight.add(c);
    const signal = AbortSignal.any ? AbortSignal.any([c.signal, AbortSignal.timeout(ms)]) : c.signal;
    return fetch(`${API}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language: lang }), signal }).finally(() => inflight.delete(c));
  }
  const cache = new Map(); // `${lang}|${text}` -> object URL: the same sentence is synthesised once
  fetch(`${API}/health`).then((r) => r.json())
    .then((h) => { if (h.voice?.kokoro?.available) serverLangs = h.voice.kokoro.languages || []; })
    .catch(() => {});

  // Silence everything at once: the playing sentence, the browser voice, every TTS request in flight
  // and whatever was queued after it (seq invalidates the rest of the paragraph).
  function stop() {
    seq++;
    for (const c of inflight) c.abort();
    inflight.clear();
    if (audio) { const a = audio; audio = null; a.onerror = null; a.pause(); // onpause resolves the awaiting sentence a.removeAttribute('src'); a.load(); }
    try { speechSynthesis.cancel(); } catch { /* not supported */ }
    onTalking(false);
  }
  // Lumi never talks to a page nobody is looking at: closing, leaving, hiding the tab or going back.
  const onHidden = () => { if (document.visibilityState === 'hidden') stop(); };
  const lifecycle = [['pagehide', stop], ['beforeunload', stop], ['popstate', stop], ['hashchange', stop]];
  if (typeof window !== 'undefined') {
    for (const [ev, fn] of lifecycle) addEventListener(ev, fn);
    document.addEventListener('visibilitychange', onHidden);
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
    const r = await request('/voice/tts/stream', text, lang, 60000);
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
      const r = await request('/voice/tts', text, lang, 30000);
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
    if (muted || !unlocked || !text || disposed || document.visibilityState === 'hidden') return;
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
      if (my === seq) speechSynthesis.speak(u);
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
    /** The app is going away: silence, and never speak again from this instance. */
    dispose() {
      disposed = true; stop();
      for (const [ev, fn] of lifecycle) removeEventListener(ev, fn);
      document.removeEventListener('visibilitychange', onHidden);
    },
    setMuted(m) { muted = m; if (m) stop(); },
    get muted() { return muted; },
  };
}
