// Lumi Live session (thread 11): token -> WebSocket to our API proxy (WS /live/ws) -> Gemini Live.
// Mic: AudioWorklet, PCM16 16 kHz binary frames up. Model: PCM16 24 kHz binary frames down, played gaplessly.
// Barge-in: the server's voice detection sends {type: 'interrupted'} and playback is flushed at once.
// Protocol: api/live.py docstring. No browser-side key: the proxy holds it.
import { OUT_RATE, int16ToFloat32, joinCaption, levelOf } from './pcm.js';

const apiBase = () => (import.meta.env?.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

export function wsUrl(base, wsPath, href = globalThis.location?.href || 'http://localhost/') {
  const u = new URL(`${base}${wsPath}`, href);
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
  return u.toString();
}

/** GET /live/status -> {available, reason, model, privacy}; never throws. */
export async function liveStatus({ base = apiBase(), fetchImpl = globalThis.fetch } = {}) {
  try {
    const r = await fetchImpl(`${base}/live/status`, { signal: AbortSignal.timeout(5000) });
    return r.ok ? await r.json() : { available: false, reason: `http_${r.status}` };
  } catch {
    return { available: false, reason: 'unreachable' };
  }
}

function createPlayer(ctx, onLevel) {
  const gain = ctx.createGain();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  gain.connect(analyser); analyser.connect(ctx.destination);
  const sources = new Set();
  const block = new Float32Array(analyser.fftSize);
  let next = 0, raf = 0, last = -1;
  const tick = () => {
    analyser.getFloatTimeDomainData(block);
    const speaking = sources.size > 0;
    const level = speaking ? levelOf(block) : 0;
    if (Math.abs(level - last) > 0.01 || (level === 0 && last !== 0)) { onLevel(level, speaking); last = level; }
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return {
    play(buffer) {
      const f = int16ToFloat32(buffer);
      if (!f.length) return;
      const ab = ctx.createBuffer(1, f.length, OUT_RATE);
      ab.copyToChannel(f, 0);
      const s = ctx.createBufferSource();
      s.buffer = ab; s.connect(gain);
      const t = Math.max(ctx.currentTime + 0.04, next);
      s.start(t); next = t + ab.duration;
      sources.add(s);
      s.onended = () => sources.delete(s);
    },
    flush() { for (const s of sources) { try { s.stop(); } catch { /* already stopped */ } } sources.clear(); next = 0; },
    get speaking() { return sources.size > 0; },
    dispose() { cancelAnimationFrame(raf); this.flush(); onLevel(0, false); },
  };
}

async function openMic(ctx, onChunk) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  // Blob URL: works in dev and in the build (a data: URL or bare asset path is not accepted everywhere)
  const { default: workletSource } = await import('./micWorklet.js?raw');
  const url = URL.createObjectURL(new Blob([workletSource], { type: 'text/javascript' }));
  try { await ctx.audioWorklet.addModule(url); } finally { URL.revokeObjectURL(url); }
  const src = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, 'live-mic');
  node.port.onmessage = (e) => onChunk(e.data.pcm, e.data.level);
  src.connect(node); // not connected to the destination: no local echo
  return { stop() { node.port.onmessage = null; src.disconnect(); node.disconnect(); stream.getTracks().forEach((t) => t.stop()); } };
}

/**
 * createLiveSession(opts) -> {start(), end(), sendText(text), sendContext(ctx), setMicMuted(bool), state}
 * opts: context, lang, on: {state(s, info), caption(role, turnText), turn({user, model, tools, grounding,
 *   interrupted, first_audio_ms}), tool(t), level(level, speaking), micLevel(level), micError(code), usage(usd),
 *   error(code, msg),
 *   ended(reason)}
 * Test seams: base, fetchImpl, WebSocketImpl, audio (false = no mic/player, for tests and text-only use).
 */
export function createLiveSession({ context = {}, lang = 'en', on = {}, base = apiBase(),
  fetchImpl = globalThis.fetch, WebSocketImpl = globalThis.WebSocket, audio = true } = {}) {
  let ws = null, ctx = null, player = null, mic = null, muted = false, closed = false, state = 'idle';
  let turn = { user: '', model: '', tools: [], interrupted: false, typed: false, t0: 0, firstAudio: null };
  const emit = (name, ...a) => { try { on[name]?.(...a); } catch (e) { console.error(e); } };
  const setState = (s, info) => { state = s; emit('state', s, info); };
  const resetTurn = () => { turn = { user: '', model: '', tools: [], interrupted: false, typed: false, t0: performance.now(), firstAudio: null }; };

  function cleanup() {
    mic?.stop(); mic = null;
    player?.dispose(); player = null;
    ctx?.close?.().catch?.(() => {}); ctx = null;
  }

  function fail(code, msg) {
    if (closed) return;
    emit('error', code, msg);
    setState('error', { code, message: msg });
    end('error');
  }

  function onMessage(ev) {
    if (typeof ev.data !== 'string') {
      if (turn.firstAudio == null) turn.firstAudio = Math.round(performance.now() - turn.t0);
      const play = (buf) => player?.play(buf);
      if (ev.data instanceof ArrayBuffer) play(ev.data); else ev.data.arrayBuffer?.().then(play);
      return;
    }
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    switch (m.type) {
      case 'ready': resetTurn(); setState('live', m); break;
      case 'caption':
        if (m.role === 'user' && !turn.user && !turn.model) turn.t0 = performance.now();
        turn[m.role === 'user' ? 'user' : 'model'] = joinCaption(turn[m.role === 'user' ? 'user' : 'model'], m.text);
        emit('caption', m.role, m.role === 'user' ? turn.user : turn.model);
        break;
      case 'tool': turn.tools.push(m); emit('tool', m); break;
      case 'interrupted': player?.flush(); turn.interrupted = true; emit('level', 0, false); break;
      case 'turn_complete':
        if (turn.user || turn.model) emit('turn', { user: turn.user.trim(), model: turn.model.trim(), tools: turn.tools,
          grounding: m.grounding, interrupted: turn.interrupted, typed: turn.typed, first_audio_ms: turn.firstAudio });
        resetTurn();
        break;
      case 'usage': emit('usage', m.cost_usd); break;
      case 'error': emit('error', 'server', m.message); break;
      case 'ended': end(m.reason || 'closed'); break;
      default: break;
    }
  }

  async function start() {
    if (state !== 'idle') return;
    setState('connecting');
    // the AudioContext must be created inside the click (autoplay rules): before any await
    if (audio) {
      try { ctx = new AudioContext(); ctx.resume?.(); } catch { return fail('audio', 'This browser cannot play audio here.'); }
    }
    let tok;
    try {
      const r = await fetchImpl(`${base}/live/token`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: { ...context, language: lang }, language: lang }) });
      tok = r.ok ? await r.json() : { available: false, reason: `http_${r.status}` };
    } catch { return fail('unreachable', 'The API is not reachable.'); }
    if (closed) return;
    if (!tok.available) return fail(tok.reason || 'unavailable', tok.reason);
    if (audio) {
      player = createPlayer(ctx, (level, speaking) => emit('level', level, speaking));
      try {
        mic = await openMic(ctx, (pcm, level) => {
          emit('micLevel', muted ? 0 : level);
          if (!muted && ws?.readyState === 1) ws.send(pcm);
        });
      } catch (e) { // no mic: the call still works, Lumi speaks and the user types
        emit('micError', e?.name === 'NotAllowedError' || e?.name === 'SecurityError' ? 'mic_denied' : 'mic', e?.message);
      }
    }
    if (closed) return;
    ws = new WebSocketImpl(wsUrl(base, tok.ws_path));
    ws.binaryType = 'arraybuffer';
    ws.onmessage = onMessage;
    ws.onerror = () => fail('socket', 'The Live connection failed.');
    ws.onclose = () => { if (!closed) end('closed'); };
  }

  function end(reason = 'user_ended') {
    if (closed) return;
    closed = true;
    try { if (ws?.readyState === 1) ws.send(JSON.stringify({ type: 'end' })); } catch { /* closing anyway */ }
    try { ws?.close(); } catch { /* already closed */ }
    cleanup();
    if (state !== 'error') setState('ended', { reason });
    emit('ended', reason);
  }

  return {
    start, end,
    sendText(text) {
      const t = String(text || '').trim();
      if (!t || ws?.readyState !== 1) return false;
      player?.flush(); resetTurn(); turn.user = t; turn.typed = true;
      ws.send(JSON.stringify({ type: 'text', text: t }));
      return true;
    },
    sendContext(c) { if (ws?.readyState === 1) ws.send(JSON.stringify({ type: 'context', context: c })); },
    setMicMuted(b) {
      muted = !!b;
      if (muted && ws?.readyState === 1) ws.send(JSON.stringify({ type: 'audio_end' }));
    },
    get state() { return state; },
  };
}
