// Lip sync for Lumi: drives lumi.setSpeaking() and lumi.setMouthLevel() from real audio.
//
//   import { attachAudio } from "../assets/character/guide/lipsync.js";
//   const detach = attachAudio(lumi, source);   // returns detach(): stops listening, mouth closes
//
// `source` can be:
//   - an <audio>/<video> element (or new Audio(url)): routed through a WebAudio AnalyserNode,
//     loudness from the waveform. Speaking follows play/pause/ended.
//   - a WebAudio AudioNode (e.g. a MediaElementSource or a gain node you already play through):
//     tapped with an analyser; speaking while it is loud enough.
//   - a MediaStream (e.g. a WebRTC voice call): same, through a MediaStreamSource.
//   - a SpeechSynthesisUtterance: the browser gives no amplitude, so the mouth flaps on the
//     word boundaries it reports (onboundary), or on a syllable timer for voices that report none.
//     Attach before speechSynthesis.speak(utterance).
//
// If WebAudio is unavailable or the audio is cross-origin without CORS (the analyser then only
// reads silence), Lumi still talks on its own rhythm while the audio plays.

const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

/** RMS of a time-domain buffer (floats in -1..1). */
export function rms(samples) {
  let sum = 0;
  for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
  return Math.sqrt(sum / (samples.length || 1));
}

/**
 * Loudness 0..1 from an RMS value: a noise gate, then a log (dB) scale so quiet consonants still
 * move the lips and loud vowels open them wide. -48 dBFS -> 0, -14 dBFS -> 1.
 */
export function levelFromRms(r, { floorDb = -48, topDb = -14 } = {}) {
  if (!(r > 0)) return 0;
  const db = 20 * Math.log10(r);
  return clamp((db - floorDb) / (topDb - floorDb), 0, 1);
}

/**
 * Syllable envelope for speech without amplitude: given syllable onset times (ms) it returns the
 * mouth level at time t: a quick open (40 ms) and a softer close (~140 ms) per syllable.
 */
export function syllableLevel(onsets, t) {
  let v = 0;
  for (const o of onsets) {
    const d = t - o.at;
    if (d < 0 || d > 400) continue;
    const env = d < 40 ? d / 40 : Math.exp(-(d - 40) / 110);
    v = Math.max(v, env * o.peak);
  }
  return v;
}

/** Rough syllable count of a word (vowel groups), at least 1. */
export function syllables(word) {
  const groups = String(word).toLowerCase().match(/[aeiouyàáâäèéêëìíîïòóôöùúûü]+/g);
  return Math.max(1, groups ? groups.length : Math.ceil(String(word).length / 3));
}

let sharedCtx = null;
const mediaSources = new WeakMap(); // an element can be wired into WebAudio only once

function audioContext() {
  if (sharedCtx) return sharedCtx;
  const AC = typeof window !== "undefined" && (window.AudioContext || window.webkitAudioContext);
  if (!AC) return null;
  try {
    sharedCtx = new AC();
  } catch {
    sharedCtx = null;
  }
  return sharedCtx;
}

const raf = (f) => (typeof requestAnimationFrame === "function" ? requestAnimationFrame(f) : setTimeout(() => f(performance.now()), 16));
const caf = (id) => (typeof cancelAnimationFrame === "function" ? cancelAnimationFrame(id) : clearTimeout(id));

/** Analyser loop: reads loudness every frame and hands it to `onLevel`. */
function analyse(ctx, input, onLevel) {
  const an = ctx.createAnalyser();
  an.fftSize = 1024;
  an.smoothingTimeConstant = 0.2;
  input.connect(an);
  const buf = new Float32Array(an.fftSize);
  let id = 0;
  let alive = true;
  const tick = () => {
    if (!alive) return;
    an.getFloatTimeDomainData(buf);
    onLevel(rms(buf));
    id = raf(tick);
  };
  id = raf(tick);
  return () => {
    alive = false;
    caf(id);
    try {
      input.disconnect(an);
    } catch {
      /* already gone */
    }
  };
}

function attachMediaElement(lumi, el) {
  const ctx = audioContext();
  let source = mediaSources.get(el) || null;
  // Wiring an element into WebAudio is permanent and it then only sounds while the context runs.
  // So it is wired only when the context is already running (never risk muting the voice);
  // otherwise this clip talks on Lumi's own rhythm and the context is resumed for the next one.
  const wire = () => {
    if (source || !ctx) return source;
    if (ctx.state !== "running") {
      ctx.resume?.().catch(() => {});
      return null;
    }
    try {
      source = ctx.createMediaElementSource(el);
      source.connect(ctx.destination); // keep it audible: the element now plays through WebAudio
      mediaSources.set(el, source);
    } catch {
      source = null; // e.g. already wired elsewhere
    }
    return source;
  };
  let heard = false; // true once real signal arrives (cross-origin audio stays silent)
  let stopAnalyse = null;
  const onLevel = (r) => {
    if (el.paused) return;
    if (r > 0.002) heard = true;
    if (heard) lumi.setMouthLevel(levelFromRms(r));
  };
  const start = () => {
    lumi.setSpeaking(true);
    if (wire() && !stopAnalyse) stopAnalyse = analyse(ctx, source, onLevel);
  };
  const stop = () => {
    lumi.setMouthLevel(0);
    lumi.setSpeaking(false);
    stopAnalyse?.();
    stopAnalyse = null;
  };
  const events = [["play", start], ["playing", start], ["pause", stop], ["ended", stop], ["emptied", stop], ["error", stop]];
  for (const [e, f] of events) el.addEventListener(e, f);
  if (!el.paused && !el.ended) start();
  return () => {
    for (const [e, f] of events) el.removeEventListener(e, f);
    stop();
  };
}

function attachNode(lumi, node) {
  const ctx = node.context;
  let quietSince = performance.now();
  let speaking = false;
  const stopAnalyse = analyse(ctx, node, (r) => {
    const level = levelFromRms(r);
    const now = performance.now();
    if (level > 0.08) {
      quietSince = now;
      if (!speaking) lumi.setSpeaking((speaking = true));
    } else if (speaking && now - quietSince > 350) lumi.setSpeaking((speaking = false)); // hold over short pauses
    if (speaking) lumi.setMouthLevel(level);
  });
  return () => {
    stopAnalyse();
    lumi.setMouthLevel(0);
    lumi.setSpeaking(false);
  };
}

function attachStream(lumi, stream) {
  const ctx = audioContext();
  if (!ctx) return () => {};
  ctx.state === "suspended" && ctx.resume().catch(() => {});
  const src = ctx.createMediaStreamSource(stream);
  const detach = attachNode(lumi, src);
  return () => {
    detach();
    try {
      src.disconnect();
    } catch {
      /* ignore */
    }
  };
}

function attachUtterance(lumi, u) {
  const rate = Number(u.rate) || 1;
  const syl = 170 / rate; // ms per syllable at this speaking rate
  let onsets = [];
  let speaking = false;
  let gotBoundary = false;
  let paused = false;
  let id = 0;
  let nextTimer = 0;
  const push = (at, peak) => {
    onsets.push({ at, peak });
    if (onsets.length > 24) onsets = onsets.slice(-24);
  };
  // a word: one quick open per syllable, louder on the first
  const word = (w, at) => {
    const n = Math.min(4, syllables(w));
    for (let i = 0; i < n; i++) push(at + i * syl, (i === 0 ? 0.85 : 0.6) + Math.random() * 0.15);
  };
  const tick = () => {
    if (!speaking) return;
    const now = performance.now();
    if (!paused && !gotBoundary && now >= nextTimer) {
      // no boundary events from this voice: a plausible syllable rhythm with short word gaps
      push(now, 0.5 + Math.random() * 0.4);
      nextTimer = now + syl * (Math.random() < 0.2 ? 2.2 : 0.8 + Math.random() * 0.5);
    }
    lumi.setMouthLevel(paused ? 0 : syllableLevel(onsets, now));
    id = raf(tick);
  };
  const onStart = () => {
    speaking = true;
    paused = false;
    onsets = [];
    nextTimer = performance.now() + 250; // give boundary events a moment to show up
    lumi.setSpeaking(true);
    caf(id);
    id = raf(tick);
  };
  const onBoundary = (e) => {
    if (e.name && e.name !== "word") return;
    gotBoundary = true;
    const text = String(u.text || "");
    const from = e.charIndex || 0;
    const len = e.charLength || (text.slice(from).match(/^\S+/) || [""])[0].length;
    word(text.slice(from, from + len) || "a", performance.now());
  };
  const onEnd = () => {
    speaking = false;
    caf(id);
    lumi.setMouthLevel(0);
    lumi.setSpeaking(false);
  };
  const onPause = () => (paused = true);
  const onResume = () => (paused = false);
  const events = [["start", onStart], ["boundary", onBoundary], ["end", onEnd], ["error", onEnd], ["pause", onPause], ["resume", onResume]];
  for (const [e, f] of events) u.addEventListener(e, f);
  return () => {
    for (const [e, f] of events) u.removeEventListener(e, f);
    onEnd();
  };
}

/**
 * Call once from a user gesture (e.g. the click that turns the voice on): creates/resumes the
 * shared AudioContext so the very first clip can already be analysed.
 */
export function unlockLipSync() {
  const ctx = audioContext();
  return ctx?.resume ? ctx.resume().catch(() => {}) : Promise.resolve();
}

/** Drive Lumi's mouth from a media element, AudioNode, MediaStream or SpeechSynthesisUtterance. Returns detach(). */
export function attachAudio(lumi, source) {
  if (!lumi || !source) return () => {};
  if (typeof HTMLMediaElement !== "undefined" && source instanceof HTMLMediaElement) return attachMediaElement(lumi, source);
  if (typeof SpeechSynthesisUtterance !== "undefined" && source instanceof SpeechSynthesisUtterance) return attachUtterance(lumi, source);
  if (typeof MediaStream !== "undefined" && source instanceof MediaStream) return attachStream(lumi, source);
  if (typeof AudioNode !== "undefined" && source instanceof AudioNode) return attachNode(lumi, source);
  throw new TypeError("attachAudio: expected an audio element, AudioNode, MediaStream or SpeechSynthesisUtterance");
}
