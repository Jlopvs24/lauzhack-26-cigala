// AudioWorklet: mic Float32 at the context rate -> Int16 mono 16 kHz chunks of ~100 ms, posted to the main thread.
// Self-contained (worklets cannot import from the app bundle).
class LiveMic extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000; // `sampleRate` is the worklet global
    this.chunk = new Int16Array(1600);
    this.fill = 0;
    this.acc = 0; this.accN = 0; this.pos = 0;
    this.sumSq = 0;
  }

  process(inputs) {
    const ch = inputs[0]?.[0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.acc += ch[i]; this.accN++; this.pos++;
      if (this.pos >= this.ratio) {
        this.pos -= this.ratio;
        const v = Math.max(-1, Math.min(1, this.acc / this.accN));
        this.acc = 0; this.accN = 0;
        this.sumSq += v * v;
        this.chunk[this.fill++] = v < 0 ? v * 0x8000 : v * 0x7fff;
        if (this.fill === this.chunk.length) {
          const level = Math.min(1, Math.sqrt(this.sumSq / this.fill) * 4);
          this.port.postMessage({ pcm: this.chunk.buffer, level }, [this.chunk.buffer]);
          this.chunk = new Int16Array(1600); this.fill = 0; this.sumSq = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor('live-mic', LiveMic);
