// Realtime "call the character" client. Framework-free so web/ can import it as is.
//
// Pipeline per turn:  browser SpeechRecognition (live, free)
//                  -> POST /agent/ask  (context.mode = "call": grounded numbers, max 2 sentences)
//                  -> POST /voice/tts/stream (sentence-by-sentence WAV, local Kokoro, free)
//                  -> gapless playback with Web Audio.
// Barge-in: while the character speaks, recognition keeps listening; if the user says
// two or more words that are not an echo of the character's own sentence, playback stops,
// pending requests are aborted, and the user's words become the next turn.
// Fallbacks: no server TTS -> speechSynthesis. No SpeechRecognition -> onUnsupported().
//
// Usage:
//   const call = new CharacterCall({ apiBase: "", getContext: () => ({ path: ["2"] }),
//     onEvent: (type, data) => console.log(type, data) });
//   await call.start();   ...   call.stop();
// Events: state {state: idle|listening|thinking|speaking}, user {text, final}, answer {answer, ...agent response},
//         sentence {index, text}, metrics {...}, error {message}, unsupported {}.

export class CharacterCall {
  constructor({ apiBase = "", getContext = () => ({}), onEvent = () => {}, language = "en-US", greeting = null } = {}) {
    this.apiBase = apiBase;
    this.getContext = getContext;
    this.emit = onEvent;
    this.language = language;
    this.greeting = greeting;
    this.history = [];
    this.active = false;
    this.speaking = false;
    this.currentSentence = "";
    this.turnId = 0;
    this.aborts = [];
    this.sources = [];
    this.audioCtx = null;
    this.rec = null;
    this.serverTts = true;
    this.fillers = [];      // [{text, buffer}] pre-synthesized, played right after the user stops
    this.fillerEnd = 0;     // AudioContext time when the current filler ends
  }

  static supported() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  async start() {
    if (!CharacterCall.supported()) { this.emit("unsupported", {}); return false; }
    this.active = true;
    this.audioCtx = this.audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    await this.audioCtx.resume();
    this._startRecognition();
    this._loadFillers(); // background, best effort
    if (this.greeting) await this._speak(this.greeting, ++this.turnId);
    else this._state("listening");
    return true;
  }

  stop() {
    this.active = false;
    this._interrupt();
    try { this.rec && this.rec.abort(); } catch (_) {}
    this.rec = null;
    this._state("idle");
  }

  // ---------------------------------------------------------------- recognition
  _startRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = this.language;
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (ev) => {
      let interim = "", final = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        if (r.isFinal) final += r[0].transcript; else interim += r[0].transcript;
      }
      const heard = (final || interim).trim();
      if (!heard) return;
      if (this.speaking && !this._isEcho(heard) && heard.split(/\s+/).length >= 2) this._bargeIn();
      if (this.speaking && this._isEcho(heard)) return; // our own voice through the speakers
      this.emit("user", { text: heard, final: !!final });
      if (final) this._turn(final.trim());
    };
    rec.onerror = (e) => { if (e.error !== "no-speech" && e.error !== "aborted") this.emit("error", { message: "speech: " + e.error }); };
    rec.onend = () => { if (this.active) { try { rec.start(); } catch (_) {} } }; // Chrome stops after silence
    rec.start();
    this.rec = rec;
  }

  _isEcho(heard) {
    const norm = (s) => s.toLowerCase().replace(/[^\p{L}\p{N} ]/gu, "").trim();
    const h = norm(heard), s = norm(this.currentSentence);
    if (!h || !s) return false;
    const words = h.split(/\s+/);
    const hits = words.filter((w) => s.includes(w)).length;
    return hits / words.length >= 0.6;
  }

  _bargeIn() {
    this._interrupt();
    this.emit("metrics", { barge_in: true });
    this._state("listening");
  }

  _interrupt() {
    this.turnId++;
    this.aborts.forEach((a) => a.abort());
    this.aborts = [];
    this.sources.forEach((s) => { try { s.stop(); } catch (_) {} });
    this.sources = [];
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    this.speaking = false;
    this.currentSentence = "";
  }

  async _loadFillers() {
    try {
      const lang = this.language.slice(0, 2);
      const { fillers } = await (await fetch(`${this.apiBase}/voice/fillers?language=${lang}`)).json();
      for (const text of fillers) {
        const r = await fetch(this.apiBase + "/voice/tts", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, language: lang }),
        });
        if (!r.ok) return; // no server TTS: no fillers
        this.fillers.push({ text, buffer: await this.audioCtx.decodeAudioData(await r.arrayBuffer()) });
      }
    } catch (_) {}
  }

  _playFiller(id) {
    if (!this.fillers.length) return;
    const f = this.fillers[Math.floor(Math.random() * this.fillers.length)];
    const src = this.audioCtx.createBufferSource();
    src.buffer = f.buffer;
    src.connect(this.audioCtx.destination);
    const at = this.audioCtx.currentTime + 0.05;
    src.start(at);
    this.fillerEnd = at + f.buffer.duration;
    this.sources.push(src);
    this.speaking = true;
    this.currentSentence = f.text;
    src.onended = () => { if (id === this.turnId && this.currentSentence === f.text) { this.speaking = false; this.currentSentence = ""; } };
  }

  // ---------------------------------------------------------------- one turn
  async _turn(question) {
    this._interrupt();
    const id = this.turnId;
    this._state("thinking");
    this._playFiller(id);
    const t0 = performance.now();
    const ctrl = new AbortController();
    this.aborts.push(ctrl);
    let res;
    try {
      const context = { ...this.getContext(), mode: "call", history: this.history.slice(-6) };
      const r = await fetch(this.apiBase + "/agent/ask", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, context }), signal: ctrl.signal,
      });
      res = await r.json();
    } catch (e) {
      if (e.name !== "AbortError") this.emit("error", { message: "agent: " + e.message });
      return;
    }
    if (id !== this.turnId) return;
    const agentMs = Math.round(performance.now() - t0);
    this.history.push({ role: "user", content: question }, { role: "assistant", content: res.answer });
    this.emit("answer", res);
    this.emit("metrics", { agent_ms: agentMs, agent_cost_usd: res.cost_usd, model: res.model, mode: res.mode });
    await this._speak(res.answer, id, res.language, t0);
  }

  // ---------------------------------------------------------------- speech out
  async _speak(text, id, language = "en", t0 = performance.now()) {
    this.speaking = true;
    this._state("speaking");
    if (this.serverTts) {
      const ok = await this._speakServer(text, id, language, t0);
      if (ok !== null) return;
      this.serverTts = false; // 503: no server TTS, use the browser from now on
    }
    await this._speakBrowser(text, id, language);
  }

  async _speakServer(text, id, language, t0) {
    const ctrl = new AbortController();
    this.aborts.push(ctrl);
    let r;
    try {
      r = await fetch(this.apiBase + "/voice/tts/stream", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language }), signal: ctrl.signal,
      });
    } catch (e) { return e.name === "AbortError" ? true : null; }
    if (r.status === 503) return null;
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "", playAt = Math.max(this.audioCtx.currentTime, this.fillerEnd), first = true, ended = Promise.resolve();
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
          if (!line.trim() || id !== this.turnId) continue;
          const msg = JSON.parse(line);
          if (msg.error) { this.emit("error", { message: "tts: " + msg.error }); continue; }
          if (msg.done) { this.emit("metrics", { tts_total_ms: msg.latency_ms, tts_cost_usd: msg.cost_usd }); continue; }
          const bytes = Uint8Array.from(atob(msg.audio_b64), (c) => c.charCodeAt(0));
          const audio = await this.audioCtx.decodeAudioData(bytes.buffer);
          if (id !== this.turnId) return true;
          const src = this.audioCtx.createBufferSource();
          src.buffer = audio;
          src.connect(this.audioCtx.destination);
          playAt = Math.max(playAt, this.audioCtx.currentTime + 0.02);
          const startDelay = (playAt - this.audioCtx.currentTime) * 1000;
          src.start(playAt);
          setTimeout(() => { if (id === this.turnId) { this.currentSentence = msg.text; this.emit("sentence", { index: msg.index, text: msg.text }); } }, startDelay);
          if (first) { first = false; this.emit("metrics", { first_audio_ms: Math.round(performance.now() - t0) }); }
          playAt += audio.duration;
          this.sources.push(src);
          ended = new Promise((res) => { src.onended = res; });
        }
      }
      await ended;
    } catch (e) {
      if (e.name !== "AbortError") this.emit("error", { message: "tts: " + e.message });
      return true;
    }
    if (id === this.turnId) { this.speaking = false; this.currentSentence = ""; this._state("listening"); }
    return true;
  }

  _speakBrowser(text, id, language) {
    return new Promise((resolve) => {
      if (!window.speechSynthesis) { this.speaking = false; this._state("listening"); return resolve(); }
      const u = new SpeechSynthesisUtterance(text);
      u.lang = language || this.language;
      this.currentSentence = text;
      u.onend = u.onerror = () => { if (id === this.turnId) { this.speaking = false; this.currentSentence = ""; this._state("listening"); } resolve(); };
      window.speechSynthesis.speak(u);
    });
  }

  _state(state) { this.emit("state", { state }); }
}
