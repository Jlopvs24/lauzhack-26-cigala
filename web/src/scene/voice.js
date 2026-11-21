// Lumi's voice. The voice always matches the language: server Kokoro (/voice/tts) only for the
// languages /health lists, else a browser voice whose lang matches, else text only (never English
// text read by a Spanish voice, or the reverse). Audio unlocks on the first user gesture.
//
// Speed under load: a paragraph is spoken sentence by sentence. The first sentence is requested
// alone (short = fast), sentence k+1 is synthesised while k plays, every sentence is cached, and the
// children's opening sentences are prefetched at low priority while the user reads. If the first
// sentence is not ready in FIRST_MS, the browser voice of the same language reads the paragraph.
import { SPEECH_LANG } from './i18n.js';

const API = (import.meta.env?.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
export const FIRST_MS = 1500;

/** Sentences as Lumi speaks them ("2.9 months" stays whole: a sentence ends at .!?… plus a space). */
export function splitSentences(text) {
  return String(text || '').split(/(?<=[.!?…])\s+/).map((s) => s.trim()).filter(Boolean);
}

/** Pick a browser voice for a language: exact locale, then same language; local voices first. */
export function pickVoice(voices, lang) {
  const want = (SPEECH_LANG[lang] || lang).toLowerCase();
  const norm = (v) => String(v.lang || '').toLowerCase().replace('_', '-');
  const rank = (v) => (norm(v) === want ? 0 : 2) + (v.localService ? 0 : 1);
  return [...voices].filter((v) => norm(v) === want || norm(v).startsWith(`${lang}-`) || norm(v) === lang)
    .sort((a, b) => rank(a) - rank(b))[0] || null;
}

const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));

// Lumi's mouth follows the voice: onLevel(0..1) at ~30 fps while speaking. Server audio goes through an
// AnalyserNode (RMS of the waveform); the browser voice has no audio stream, so each word boundary is a pulse.
export function levelFromSamples(buf) {
  let sum = 0;
  for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
  return Math.min(1, Math.sqrt(sum / (buf.length || 1)) * 4.5);
}

export function createVoice({ onTalking = () => {}, onNoVoice = () => {}, onLevel = () => {} } = {}) {
  let unlocked = false, muted = false, audio = null, seq = 0, serverLangs = [], disposed = false;
  let preGen = 0, fgPending = 0;
  const hasSpeech = typeof window !== 'undefined' && 'speechSynthesis' in window;
  const health = fetch(`${API}/health`).then((r) => r.json())
    .then((h) => { if (h.voice?.kokoro?.available) serverLangs = h.voice.kokoro.languages || []; })
    .catch(() => {});
  // Browser voices load late in Chrome (getVoices() is [] until 'voiceschanged').
  let voices = hasSpeech ? speechSynthesis.getVoices() : [];
  const voicesReady = !hasSpeech ? Promise.resolve() : voices.length ? Promise.resolve() : new Promise((ok) => {
    const on = () => { voices = speechSynthesis.getVoices(); if (voices.length) { speechSynthesis.removeEventListener?.('voiceschanged', on); ok(); } };
    speechSynthesis.addEventListener?.('voiceschanged', on);
    setTimeout(ok, 1500);
  });
  const browserVoice = (lang) => (hasSpeech ? pickVoice(voices.length ? voices : (voices = speechSynthesis.getVoices()), lang) : null);

  // ---------- sentence cache: `${lang}|${sentence}` -> Promise<object URL> ----------
  const cache = new Map();
  const ctls = new Map(); // AbortController -> 'fg' | 'low'
  function synth(sentence, lang, low = false) {
    const key = `${lang}|${sentence}`;
    const hit = cache.get(key);
    if (hit) { cache.delete(key); cache.set(key, hit); return hit.p; } // LRU touch
    const c = new AbortController(); ctls.set(c, low ? 'low' : 'fg');
    if (!low) fgPending++;
    const signal = AbortSignal.any ? AbortSignal.any([c.signal, AbortSignal.timeout(30000)]) : c.signal;
    const entry = {};
    entry.p = fetch(`${API}/voice/tts`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: sentence, language: lang }), signal, priority: low ? 'low' : 'high' })
      .then(async (r) => { if (!r.ok) throw new Error(`tts ${r.status}`); return (entry.url = URL.createObjectURL(await r.blob())); })
      .catch((e) => { if (cache.get(key) === entry) cache.delete(key); throw e; })
      .finally(() => { ctls.delete(c); if (!low) fgPending--; });
    entry.p.catch(() => {});
    cache.set(key, entry);
    while (cache.size > 160) { const [k, e] = cache.entries().next().value; if (e.url) URL.revokeObjectURL(e.url); cache.delete(k); }
    return entry.p;
  }
  function abort(kind) { for (const [c, k] of ctls) if (!kind || k === kind) { c.abort(); ctls.delete(c); } }

  // Silence everything at once: the playing sentence, the browser voice, every foreground TTS
  // request and the rest of the paragraph (seq invalidates it).
  function stop() {
    seq++;
    abort('fg');
    if (audio) { // pause() fires onpause, which resolves the sentence being awaited
      const a = audio; audio = null; a.onerror = null; a.pause(); a.removeAttribute('src'); a.load();
    }
    try { speechSynthesis.cancel(); } catch { /* not supported */ }
    speaking = false; pulse = 0;
    onTalking(false);
  }
  function cancelPrefetch() { preGen++; abort('low'); }
  // Lumi never talks to a page nobody is looking at: closing, leaving, hiding the tab or going back.
  const silenceAll = () => { stop(); cancelPrefetch(); };
  const onHidden = () => { if (document.visibilityState === 'hidden') silenceAll(); };
  const lifecycle = [['pagehide', silenceAll], ['beforeunload', silenceAll], ['popstate', stop], ['hashchange', stop]];
  if (typeof window !== 'undefined') {
    for (const [ev, fn] of lifecycle) addEventListener(ev, fn);
    document.addEventListener('visibilitychange', onHidden);
  }

  // ---------- mouth level ----------
  let actx = null, analyser = null, samples = null, meterRaf = 0, lastEmit = 0, level = 0, pulse = 0;
  function ensureAnalyser() {
    if (analyser || typeof window === 'undefined' || !(window.AudioContext || window.webkitAudioContext)) return analyser;
    try {
      actx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = actx.createAnalyser(); analyser.fftSize = 512; analyser.smoothingTimeConstant = 0.5;
      analyser.connect(actx.destination);
      samples = new Uint8Array(analyser.fftSize);
    } catch { analyser = null; }
    return analyser;
  }
  function meter(now) {
    meterRaf = 0;
    let target = 0;
    if (audio && !audio.paused && analyser) { analyser.getByteTimeDomainData(samples); target = levelFromSamples(samples); }
    pulse *= 0.82; // word pulses (browser voice) decay between boundaries
    target = Math.max(target, pulse);
    level += (target - level) * (target > level ? 0.6 : 0.3);
    if (now - lastEmit > 30) { lastEmit = now; onLevel(level < 0.02 ? 0 : level); }
    if (level > 0.01 || (audio && !audio.paused) || speaking) meterRaf = requestAnimationFrame(meter);
    else onLevel(0);
  }
  let speaking = false;
  const startMeter = () => { if (!meterRaf && typeof requestAnimationFrame !== 'undefined') meterRaf = requestAnimationFrame(meter); };
  function playUrl(url, my) {
    return new Promise((resolve, reject) => {
      if (my !== seq) return resolve();
      audio = new Audio(url);
      if (ensureAnalyser() && actx.state === 'running') { // a suspended context would mute the clip
        try { actx.resume?.(); actx.createMediaElementSource(audio).connect(analyser); } catch { /* plays unmetered */ }
      }
      audio.addEventListener('play', startMeter);
      audio.onplay = () => onTalking(true);
      audio.onended = () => resolve();
      audio.onpause = () => resolve();
      audio.onerror = () => reject(new Error('audio'));
      audio.play().catch(reject);
    });
  }
  function browserSpeak(sentences, v, my) {
    if (my !== seq || !sentences.length) return;
    sentences.forEach((s, i) => { // one utterance per sentence: Chrome cuts long utterances short
      const u = new SpeechSynthesisUtterance(s);
      u.voice = v; u.lang = v.lang; u.rate = 1.02;
      if (i === 0) u.onstart = () => { speaking = true; pulse = 0.7; startMeter(); onTalking(true); };
      u.onboundary = (e) => { if (e.name !== 'sentence') { pulse = 0.55 + Math.random() * 0.4; startMeter(); } };
      if (i === sentences.length - 1) u.onend = () => { speaking = false; onTalking(false); };
      u.onerror = () => { speaking = false; onTalking(false); };
      if (my === seq) speechSynthesis.speak(u);
    });
  }

  async function speak(text, lang) {
    stop();
    if (muted || !unlocked || !text || disposed || document.visibilityState === 'hidden') return;
    const my = seq;
    const parts = splitSentences(text);
    await Promise.race([health, sleep(600)]);
    if (my !== seq) return;
    if (!serverLangs.includes(lang)) { // e.g. German: no Kokoro voice, the OS/Chrome voice reads it
      await voicesReady;
      if (my !== seq) return;
      const v = browserVoice(lang);
      if (v) browserSpeak(parts, v, my); else onNoVoice(lang);
      return;
    }
    // first sentence as soon as possible; the browser voice takes over if the server is slow
    const first = synth(parts[0], lang);
    const ready = await Promise.race([first.then(() => true, () => false), sleep(FIRST_MS).then(() => null)]);
    if (my !== seq) return;
    if (ready !== true) {
      const v = browserVoice(lang);
      if (v) { browserSpeak(parts, v, my); return; }
      if (ready === false) { onNoVoice(lang); return; }
    }
    for (let k = 0; k < parts.length; k++) {
      let url;
      try { url = await synth(parts[k], lang); } catch {
        if (my !== seq) return;
        const v = browserVoice(lang); // mid-paragraph failure: the browser finishes the paragraph
        if (v) browserSpeak(parts.slice(k), v, my); else onTalking(false);
        return;
      }
      if (my !== seq) return;
      if (parts[k + 1]) synth(parts[k + 1], lang).catch(() => {}); // next sentence while this one plays
      try { await playUrl(url, my); } catch { /* a broken clip: skip to the next sentence */ }
      if (my !== seq) return;
    }
    onTalking(false);
  }

  /** Warm the cache with what Lumi will probably say next (children's openings). Low priority,
   *  one request at a time, only while no narration is being synthesised; cancelled on navigation. */
  async function prefetch(texts, lang) {
    cancelPrefetch();
    const g = preGen;
    await Promise.race([health, sleep(600)]);
    if (muted || disposed || !serverLangs.includes(lang)) return;
    const todo = [...new Set(texts.flatMap(splitSentences))].filter((s) => !cache.has(`${lang}|${s}`));
    for (const s of todo) {
      while (fgPending > 0) { if (g !== preGen) return; await sleep(250); }
      if (g !== preGen || disposed || document.visibilityState === 'hidden') return;
      try { await synth(s, lang, true); } catch { /* aborted or failed: never mind */ }
    }
  }

  return {
    unlock() {
      if (unlocked) return;
      unlocked = true;
      try { const a = new Audio(); a.muted = true; a.play().catch(() => {}); } catch { /* ignore */ }
      try { ensureAnalyser(); actx?.resume?.(); } catch { /* ignore */ } // created inside the gesture: never suspended
      try { speechSynthesis.speak(new SpeechSynthesisUtterance('')); } catch { /* ignore */ }
    },
    speak, stop, prefetch, cancelPrefetch,
    /** The app is going away: silence, and never speak again from this instance. */
    dispose() {
      disposed = true; silenceAll();
      for (const [ev, fn] of lifecycle) removeEventListener(ev, fn);
      document.removeEventListener('visibilitychange', onHidden);
    },
    setMuted(m) { muted = m; if (m) { stop(); cancelPrefetch(); } },
    get muted() { return muted; },
  };
}
