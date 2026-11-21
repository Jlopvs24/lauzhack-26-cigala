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

// demo.html inlines the module and the CSS so it opens straight from disk (file://)
const js = readFileSync(join(here, "guide.js"), "utf8").replace(/^export /gm, "");
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
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 18px;max-width:860px}
.stage{position:relative;height:300px;background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden;margin-bottom:14px}
.stage .ground{position:absolute;left:0;right:0;bottom:40px;border-top:3px solid #D9D2BF}
.stage .leaf{position:absolute;right:24px;top:40px;width:210px;padding:12px 14px;border-radius:14px;background:#fff;border:1px solid var(--line);font-size:13px;color:var(--muted)}
.stage .leaf b{color:var(--ink)}
#lumi{position:absolute;left:24px;top:60px}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:6px 14px;cursor:pointer}
button[aria-pressed=true]{background:var(--ink);color:#fff;border-color:var(--ink)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}
figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 4px;text-align:center}
figure svg{width:100%;max-width:120px;height:auto}
figcaption{font-size:12px;color:var(--muted)}
${css}
</style></head><body>
<h1>Lumi, the guide</h1>
<p class="sub">A soft glowing orb that floats next to the tree and explains it. It never recommends or decides. Its colour, glow and face follow the health of the selected node. Try the controls: health, pose, talking, and gliding to the leaf it explains.</p>
<div class="stage"><div class="ground"></div><div class="leaf"><b>Master's in Lausanne</b><br>Cash runs out in month 7 in the median path. Range: month 5 to 10.</div><div id="lumi"></div></div>
<div class="controls">
  <button data-health="healthy" aria-pressed="true">Healthy</button>
  <button data-health="fair">Fair</button>
  <button data-health="weak">Weak</button>
  <button id="explain">Explain the leaf</button>
  <button id="talk">Talk</button>
</div>
<div class="grid">
${grid}
</div>
<script>
${js}
const el = document.getElementById("lumi");
const lumi = createGuide(el);
document.querySelectorAll("[data-health]").forEach((b) => b.onclick = () => {
  lumi.setHealth(b.dataset.health);
  document.querySelectorAll("[data-health]").forEach((x) => x.setAttribute("aria-pressed", x === b));
});
let away = false;
document.getElementById("explain").onclick = (e) => {
  away = !away;
  const stage = el.parentElement;
  lumi.moveTo(away ? stage.clientWidth - 24 - 210 - 24 - 140 - 24 : 0, away ? -30 : 0);
  lumi.setPose(away ? "explaining" : "idle");
  lumi.setTalking(away);
  e.currentTarget.setAttribute("aria-pressed", away);
};
let talking = false;
document.getElementById("talk").onclick = (e) => { talking = !talking; lumi.setTalking(talking); e.currentTarget.setAttribute("aria-pressed", talking); };
</script>
</body></html>
`;
writeFileSync(join(here, "demo.html"), page);
console.log("wrote states/*.svg and demo.html");
