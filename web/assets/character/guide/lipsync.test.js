// Run: node --test web/assets/character/guide/*.test.js
import test from "node:test";
import assert from "node:assert/strict";

// A minimal SpeechSynthesisUtterance for Node (the real one only exists in browsers).
globalThis.SpeechSynthesisUtterance ??= class extends EventTarget {
  constructor(text) {
    super();
    this.text = text;
    this.rate = 1;
  }
};

const { rms, levelFromRms, syllableLevel, syllables, attachAudio } = await import("./lipsync.js");
const { mouthShape, moodToHealth } = await import("./guide.js");

const fakeLumi = () => {
  const log = { speaking: [], levels: [] };
  return { log, setSpeaking: (on) => log.speaking.push(on), setMouthLevel: (v) => log.levels.push(v) };
};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

test("rms of silence, a full-scale square wave and a half sine", () => {
  assert.equal(rms(new Float32Array(64)), 0);
  assert.equal(rms(Float32Array.from({ length: 64 }, (_, i) => (i % 2 ? 1 : -1))), 1);
  const sine = Float32Array.from({ length: 1000 }, (_, i) => 0.5 * Math.sin((i / 1000) * Math.PI * 20));
  assert.ok(Math.abs(rms(sine) - 0.5 / Math.SQRT2) < 0.01);
});

test("levelFromRms: gate below -48 dB, saturates at -14 dB, monotonic in between", () => {
  assert.equal(levelFromRms(0), 0);
  assert.equal(levelFromRms(0.001), 0); // -60 dB: room noise stays closed
  assert.equal(levelFromRms(0.5), 1);
  const a = levelFromRms(0.01);
  const b = levelFromRms(0.05);
  assert.ok(a > 0 && b > a && b < 1);
});

test("syllables counts vowel groups", () => {
  assert.equal(syllables("cash"), 1);
  assert.equal(syllables("median"), 2); // e-ia: vowel groups, close enough for lips
  assert.equal(syllables("Lausanne"), 3); // vowel groups, silent e included: fine for lips
  assert.equal(syllables("7"), 1);
});

test("syllableLevel: opens fast, closes softly, zero before and long after", () => {
  const on = [{ at: 1000, peak: 1 }];
  assert.equal(syllableLevel(on, 990), 0);
  assert.ok(syllableLevel(on, 1040) > 0.99);
  const mid = syllableLevel(on, 1150);
  assert.ok(mid > 0.2 && mid < 0.6);
  assert.equal(syllableLevel(on, 1500), 0);
});

test("mouthShape: closed near 0, opens with level, tongue only when open", () => {
  const quiet = mouthShape(0);
  const mid = mouthShape(0.5);
  const loud = mouthShape(1);
  assert.ok(quiet.open < 1.2 && quiet.tongue === 0);
  assert.ok(mid.open > quiet.open && loud.open > mid.open);
  assert.ok(loud.tongue > 0.9);
  // round vowels are narrower than wide ones at the same loudness
  assert.ok(mouthShape(0.9, 1).w < mouthShape(0.9, 0).w);
});

test("moodToHealth maps engine scores and levels", () => {
  assert.equal(moodToHealth(85), "healthy");
  assert.equal(moodToHealth(55), "fair");
  assert.equal(moodToHealth(12), "weak");
  assert.equal(moodToHealth("fragile"), "weak");
});

test("utterance with word boundaries drives speaking and the mouth level", async () => {
  const lumi = fakeLumi();
  const u = new SpeechSynthesisUtterance("Cash runs out in month seven");
  const detach = attachAudio(lumi, u);
  u.dispatchEvent(new Event("start"));
  const b = new Event("boundary");
  Object.assign(b, { name: "word", charIndex: 0, charLength: 4 });
  u.dispatchEvent(b);
  await wait(80);
  assert.deepEqual(lumi.log.speaking, [true]);
  assert.ok(Math.max(...lumi.log.levels) > 0.5, "mouth opened on the word");
  u.dispatchEvent(new Event("end"));
  assert.equal(lumi.log.speaking.at(-1), false);
  assert.equal(lumi.log.levels.at(-1), 0);
  detach();
});

test("utterance without boundary events falls back to a syllable timer", async () => {
  const lumi = fakeLumi();
  const u = new SpeechSynthesisUtterance("Hello there");
  const detach = attachAudio(lumi, u);
  u.dispatchEvent(new Event("start"));
  await wait(600);
  const opened = lumi.log.levels.filter((v) => v > 0.3).length;
  assert.ok(opened > 3, `expected the timer to open the mouth, got ${opened} open frames`);
  detach();
  assert.equal(lumi.log.speaking.at(-1), false);
});

test("attachAudio rejects unknown sources and ignores missing ones", () => {
  assert.throws(() => attachAudio(fakeLumi(), {}), TypeError);
  assert.equal(typeof attachAudio(fakeLumi(), null), "function");
});
