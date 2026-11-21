// PCM helpers for Lumi Live (pure, tested in pcm.test.js).
// Mic: Float32 at the AudioContext rate -> Int16 mono 16 kHz. Model audio: Int16 mono 24 kHz -> Float32.

export const IN_RATE = 16000;
export const OUT_RATE = 24000;

/** Downsample Float32 samples from `from` Hz to `to` Hz (box average, fine for speech) and convert to Int16. */
export function downsampleToInt16(input, from, to = IN_RATE) {
  if (!input?.length) return new Int16Array(0);
  const ratio = from / to;
  const n = Math.floor(input.length / ratio);
  const out = new Int16Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * ratio), b = Math.min(input.length, Math.floor((i + 1) * ratio)) || a + 1;
    let sum = 0;
    for (let j = a; j < b; j++) sum += input[j];
    const v = Math.max(-1, Math.min(1, sum / Math.max(1, b - a)));
    out[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  return out;
}

/** Int16 little-endian bytes (ArrayBuffer) -> Float32 in [-1, 1]. */
export function int16ToFloat32(buffer) {
  const view = new DataView(buffer);
  const n = Math.floor(buffer.byteLength / 2);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = view.getInt16(i * 2, true) / 0x8000;
  return out;
}

/** Mouth opening 0-1 from a block of Float32 samples (RMS with a speech-friendly gain). */
export function levelOf(samples) {
  if (!samples?.length) return 0;
  let sum = 0;
  for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
  return Math.min(1, Math.sqrt(sum / samples.length) * 4);
}

/** Captions arrive in pieces; join them without doubled or missing spaces. */
export function joinCaption(prev, piece) {
  if (!piece) return prev;
  if (!prev) return piece.trimStart();
  if (/\s$/.test(prev) || /^[\s,.;:!?)]/.test(piece)) return prev + piece;
  return `${prev} ${piece}`;
}
