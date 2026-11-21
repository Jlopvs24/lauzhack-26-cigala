// Writes the static state images and the self-contained demo page.
// Run: node web/assets/character/guide/export.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { guideSVG, HEALTHS, POSES } from "./guide.js";

const here = dirname(fileURLToPath(import.meta.url));
const states = join(here, "states");
mkdirSync(states, { recursive: true });

for (const health of HEALTHS)
  for (const pose of POSES)
    writeFileSync(join(states, `lumi-${health}-${pose}.svg`), guideSVG({ health, pose, id: `lumi-${health}-${pose}` }) + "\n");

// demo.html inlines the modules and the CSS so it opens straight from disk (file://).
// Each module goes in its own function scope (they share helper names) and returns its exports.
const inline = (file, names) =>
  `(() => {\n${readFileSync(join(here, file), "utf8").replace(/^export /gm, "")}\nreturn { ${names.join(", ")} };\n})()`;
const guideMod = inline("guide.js", ["createGuide"]);
const lipMod = inline("lipsync.js", ["attachAudio", "unlockLipSync"]);
const css = readFileSync(join(here, "guide.css"), "utf8");
const grid = HEALTHS.flatMap((h) =>
  POSES.map((p) => `<figure>${guideSVG({ health: h, pose: p, id: `g-${h}-${p}` })}<figcaption>${h} · ${p}</figcaption></figure>`),
).join("\n");

const page = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lumi guide demo</title>
<style>
:root{--bg:#F6F3EA;--card:#FFFDF7;--ink:#1F2B4D;--muted:#69708A;--line:#E4DFD0}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:26px 0 4px}.sub{color:var(--muted);margin:0 0 18px;max-width:860px}
.stage{position:relative;height:340px;background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden;margin-bottom:14px}
.stage .ground{position:absolute;left:0;right:0;bottom:40px;border-top:3px solid #D9D2BF}
.stage .leaf{position:absolute;right:24px;top:40px;width:210px;padding:12px 14px;border-radius:14px;background:#fff;border:1px solid var(--line);font-size:13px;color:var(--muted)}
.stage .leaf b{color:var(--ink)}
#lumi{position:absolute;left:24px;top:110px}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;align-items:center}
button,.file{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:6px 14px;cursor:pointer}
.file input{display:none}
button[aria-pressed=true]{background:var(--ink);color:#fff;border-color:var(--ink)}
.dock{position:relative;height:220px;background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden;margin-bottom:14px}
.dock .chatline{position:absolute;left:16px;right:16px;bottom:14px;height:40px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--muted);font-size:13px;display:flex;align-items:center;padding:0 16px}
.dock .slot{position:absolute;bottom:64px;display:flex;flex-direction:column;align-items:center;gap:2px;font-size:11px;color:var(--muted)}
.meter{width:160px;height:8px;border-radius:999px;background:var(--line);overflow:hidden}.meter i{display:block;height:100%;width:0;background:#5CC39A}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}
figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 4px;text-align:center}
figure svg{width:100%;max-width:120px;height:auto}
figcaption{font-size:12px;color:var(--muted)}
${css}
</style></head><body>
<h1>Lumi, the guide</h1>
<p class="sub">A soft glowing orb that floats next to the tree and explains it. It never recommends or decides. Its colour, glow and face follow the health of the selected node. Bring the mouse close (it watches you and slightly dodges), click it (spin and hop), leave it alone for 25 s (it dozes off), or use the controls.</p>
<div class="stage"><div class="ground"></div><div class="leaf" id="leaf"><b>Master's in Lausanne</b><br>Cash runs out in month 7 in the median path. Range: month 5 to 10.</div><div id="lumi"></div></div>
<div class="controls">
  <button data-score="85" aria-pressed="true">setMood(85)</button>
  <button data-score="55">setMood(55)</button>
  <button data-score="20">setMood(20)</button>
  <button id="explain">Explain the leaf</button>
  <button id="say">say(...)</button>
</div>

<h2>Lip sync, docked at 64 / 80 / 96 px</h2>
<p class="sub">The mouth follows the voice: a WebAudio analyser reads the loudness of an audio element, node or stream; speechSynthesis has no amplitude, so the mouth flaps on word boundaries (or a syllable timer). Blinking continues while it talks.</p>
<div class="dock">
  <div class="slot" style="right:236px"><div id="d64" style="width:64px"></div>64 px</div>
  <div class="slot" style="right:128px"><div id="d80" style="width:80px"></div>80 px</div>
  <div class="slot" style="right:16px"><div id="d96" style="width:96px"></div>96 px</div>
  <div class="chatline">Ask Lumi about your tree…</div>
</div>
<div class="controls">
  <button id="synth">Speech-like audio (AnalyserNode)</button>
  <button id="tts">speechSynthesis (word boundaries)</button>
  <label class="file">Play an audio file (audio element)<input id="file" type="file" accept="audio/*"></label>
  <span class="meter" aria-hidden="true"><i id="meter"></i></span>
</div>

<h2>All states</h2>
<div class="grid">
${grid}
</div>
<script>
const { createGuide } = ${guideMod};
const { attachAudio, unlockLipSync } = ${lipMod};

// ---- main stage
const el = document.getElementById("lumi");
const lumi = createGuide(el, { mood: 85 });
document.querySelectorAll("[data-score]").forEach((b) => b.onclick = () => {
  for (const g of [lumi, ...docked]) g.setMood(Number(b.dataset.score));
  document.querySelectorAll("[data-score]").forEach((x) => x.setAttribute("aria-pressed", x === b));
});
let away = false;
document.getElementById("explain").onclick = async (e) => {
  away = !away;
  e.currentTarget.setAttribute("aria-pressed", away);
  const stage = el.parentElement;
  if (!away) { lumi.say(""); lumi.pointAt(null); lumi.moveTo(0, 0); return; }
  lumi.moveTo(stage.clientWidth - 24 - 210 - 24 - 140 - 40, 0);
  lumi.pointAt(document.getElementById("leaf"));
  await lumi.say("In the median path, cash runs out in month 7. In most futures it happens between month 5 and 10.");
  if (away) lumi.pointAt(null);
};
document.getElementById("say").onclick = () => lumi.say("Hi! I explain your tree. You decide.");

// ---- docked guides + lip sync (all three follow the same audio)
const docked = ["d64", "d80", "d96"].map((id) => createGuide(document.getElementById(id), { mood: 85 }));
const meter = document.getElementById("meter");
const all = { setSpeaking: (on) => docked.forEach((g) => g.setSpeaking(on)), setMouthLevel: (v) => { meter.style.width = (v * 100).toFixed(0) + "%"; docked.forEach((g) => g.setMouthLevel(v)); } };
let detach = () => {};

// speech-like test signal: a buzzy voice with syllable-shaped loudness and short word gaps
document.getElementById("synth").onclick = async () => {
  detach();
  await unlockLipSync();
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const osc = ctx.createOscillator(); osc.type = "sawtooth"; osc.frequency.value = 150;
  const filt = ctx.createBiquadFilter(); filt.type = "lowpass"; filt.frequency.value = 900;
  const amp = ctx.createGain(); amp.gain.value = 0;
  osc.connect(filt).connect(amp).connect(ctx.destination);
  let t = ctx.currentTime + 0.05;
  for (let w = 0; w < 9; w++) {
    const n = 1 + Math.floor(Math.random() * 3);
    for (let i = 0; i < n; i++) {
      const peak = 0.12 + Math.random() * 0.22;
      amp.gain.setValueAtTime(0.0001, t);
      amp.gain.linearRampToValueAtTime(peak, t + 0.04);
      amp.gain.exponentialRampToValueAtTime(0.002, t + 0.16 + Math.random() * 0.06);
      osc.frequency.setValueAtTime(130 + Math.random() * 60, t);
      t += 0.19;
    }
    t += 0.12 + Math.random() * 0.15;
  }
  osc.start(); osc.stop(t + 0.1);
  detach = attachAudio(all, amp);
  osc.onended = () => { detach(); ctx.close(); };
};

document.getElementById("tts").onclick = () => {
  detach();
  if (!("speechSynthesis" in window)) return alert("speechSynthesis is not available in this browser");
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance("Hi! I am Lumi. In the median path, cash runs out in month seven. You decide what to do.");
  u.lang = "en-US";
  detach = attachAudio(all, u);
  speechSynthesis.speak(u);
};

document.getElementById("file").onchange = async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  detach();
  await unlockLipSync();
  const a = new Audio(URL.createObjectURL(f));
  detach = attachAudio(all, a);
  a.play();
};
</script>
</body></html>
`;
writeFileSync(join(here, "demo.html"), page);
console.log("wrote states/*.svg and demo.html");
