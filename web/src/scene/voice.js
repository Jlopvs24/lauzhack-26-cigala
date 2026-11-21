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
  async function speak(text, lang) {
    stop();
    if (muted || !unlocked || !text) return;
    const my = seq;
    try {
      if (!serverLangs.includes(lang)) throw new Error(`no server voice for ${lang}`);
      const key = `${lang}|${text}`;
      let url = cache.get(key);
      if (!url) {
        const r = await fetch(`${API}/voice/tts`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, language: lang }), signal: AbortSignal.timeout(12000) });
        if (!r.ok) throw new Error(`tts ${r.status}`);
        url = URL.createObjectURL(await r.blob());
        if (cache.size > 40) { const [k, u] = cache.entries().next().value; URL.revokeObjectURL(u); cache.delete(k); }
        cache.set(key, url);
      }
      if (my !== seq) return;
      audio = new Audio(url);
      audio.onplay = () => onTalking(true);
      audio.onended = audio.onpause = () => onTalking(false);
      await audio.play();
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
