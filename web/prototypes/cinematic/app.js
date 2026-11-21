// Track B prototype: a photoreal tree made of matched AI stills.
// The "world" is the master photo's pixel space (1376 x 768). Every close-up still was generated
// from an exact crop of its parent, so it sits on a known rectangle of that world. The camera flies
// between rectangles; the higher-detail still fades in on top as we arrive, so the zoom is seamless.
// Greying uses a per-still label map (limb*10 + sub-branch) computed offline (see README.md).
import { createGuide } from "../../assets/character/guide/guide.js";

const qs = new URLSearchParams(location.search);
const API = qs.get("api") || "http://127.0.0.1:8002";
const W = 1376, H = 768;
const $ = (s) => document.querySelector(s);
const gsap = window.gsap;
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------- world geometry ----------
const meta = await (await fetch("img/stills.json")).json();
const rectOf = (name) => { const [x, y, w, h] = meta[name].rect; return { x, y, w, h }; };
const CROWN = { 1: [420, 215], 2: [675, 92], 3: [965, 228] };
const DEPTH3 = [[0.27, 0.42], [0.5, 0.28], [0.73, 0.44]];

const parts = (id) => String(id).split(".").map(Number);
function stillFor(id) {
  if (!id || id === "0") return "master";
  const p = parts(id);
  if (p.some((n) => !(n >= 1 && n <= 3))) return null;
  if (p.length === 1) return `c${p[0]}`;
  return `c${p[0]}_${p[1]}`; // depth 3+ reuses its depth-2 still
}
function viewRect(id) {
  if (!id || id === "0") return { x: 0, y: 0, w: W, h: H };
  const p = parts(id);
  if (p.length <= 2 && stillFor(id)) return rectOf(stillFor(id));
  const base = viewRect(p.slice(0, 2).join("."));
  const [fx, fy] = DEPTH3[(p[2] - 1) % 3] || [0.5, 0.5];
  const w = base.w * 0.58, h = base.h * 0.58;
  return { x: base.x + base.w * fx - w / 2, y: base.y + base.h * fy - h / 2, w, h };
}
function anchor(id) {
  if (id === "0") return [688, 560];
  const p = parts(id);
  if (p.length === 1) return CROWN[p[0]] || [688, 200];
  if (p.length === 2) return meta.hot[p[0]]?.[p[1] - 1] || CROWN[p[0]];
  const r = viewRect(p.slice(0, 2).join("."));
  const [fx, fy] = DEPTH3[(p[2] - 1) % 3] || [0.5, 0.5];
  return [r.x + r.w * fx, r.y + r.h * fy];
}
// label-map codes for a node: a limb covers its three sub-branches
function codes(id) {
  const p = parts(id);
  if (p.length === 1) return [p[0] * 10 + 1, p[0] * 10 + 2, p[0] * 10 + 3];
  if (p.length === 2) return [p[0] * 10 + p[1]];
  return [];
}

// ---------- stills (base canvas + grey overlay canvas) ----------
const stage = $("#stage"), world = $("#world");
const stills = {};
function loadImg(src) { return new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = src; }); }
function getStill(name) {
  if (stills[name]) return stills[name];
  const el = document.createElement("div");
  el.className = name === "master" ? "still master" : "still";
  el.style.zIndex = name === "master" ? 0 : name.includes("_") ? 2 : 1;
  const base = document.createElement("canvas"), grey = document.createElement("canvas");
  grey.className = "grey";
  el.append(base, grey);
  world.append(el);
  const s = { name, el, base, grey, rect: rectOf(name), on: false, greyKey: "" };
  s.ready = Promise.all([loadImg(`img/${name}.webp`), loadImg(`img/${name}.lab.png`)]).then(([img, lab]) => {
    for (const c of [base, grey]) { c.width = img.naturalWidth; c.height = img.naturalHeight; }
    base.getContext("2d").drawImage(img, 0, 0);
    s.rgb = base.getContext("2d").getImageData(0, 0, base.width, base.height);
    const t = document.createElement("canvas"); t.width = base.width; t.height = base.height;
    const tc = t.getContext("2d"); tc.drawImage(lab, 0, 0, t.width, t.height);
    s.lab = tc.getImageData(0, 0, t.width, t.height).data;
  });
  stills[name] = s;
  return s;
}
function paintGrey(s, set) {
  const key = [...set].sort().join(",");
  if (s.greyKey === key) return;
  s.greyKey = key;
  const w = s.grey.width, h = s.grey.height;
  if (!s.desat) { // whole frame desaturated and lifted toward the mist (sky barely changes)
    s.desat = document.createElement("canvas"); s.desat.width = w; s.desat.height = h;
    const o = new ImageData(w, h), src = s.rgb.data, d = o.data;
    for (let i = 0; i < d.length; i += 4) {
      const v = (0.3 * src[i] + 0.59 * src[i + 1] + 0.11 * src[i + 2]) * 0.64 + 212 * 0.36;
      d[i] = v + 2; d[i + 1] = v + 3; d[i + 2] = v + 6; d[i + 3] = 255;
    }
    s.desat.getContext("2d").putImageData(o, 0, 0);
  }
  // region mask at 1/4 resolution, feathered with a blur so limb boundaries melt instead of cutting
  const q = 4, mw = Math.ceil(w / q), mh = Math.ceil(h / q);
  const m = document.createElement("canvas"); m.width = mw; m.height = mh;
  const md = new ImageData(mw, mh), lab = s.lab;
  for (let y = 0; y < mh; y++) for (let x = 0; x < mw; x++) {
    if (set.has(lab[((y * q) * w + x * q) * 4])) md.data[(y * mw + x) * 4 + 3] = 255;
  }
  m.getContext("2d").putImageData(md, 0, 0);
  const ctx = s.grey.getContext("2d");
  ctx.save();
  ctx.clearRect(0, 0, w, h);
  ctx.drawImage(s.desat, 0, 0);
  ctx.globalCompositeOperation = "destination-in";
  ctx.filter = `blur(${Math.round(w / 60)}px)`;
  ctx.drawImage(m, 0, 0, w, h);
  ctx.restore();
  if (!reduced) gsap.fromTo(s.grey, { opacity: 0 }, { opacity: 1, duration: 1.1, ease: "power2.out" });
  else s.grey.style.opacity = 1;
}

// ---------- camera ----------
const cam = { cx: 688, cy: 384, z: 1 };       // z = screen px per world unit
const look = { x: 0, y: 0, tx: 0, ty: 0 };     // bounded free look (pointer parallax)
let flying = false;
function fitZ(r) { return Math.max(innerWidth / r.w, innerHeight / r.h); }
function camTo(r, { duration = 1.8, ease = "power3.inOut" } = {}) {
  const from = { ...cam }, to = { cx: r.x + r.w / 2, cy: r.y + r.h / 2, z: fitZ(r) };
  if (reduced) duration = 0.01;
  flying = true;
  const o = { t: 0 };
  return new Promise((done) => gsap.to(o, {
    t: 1, duration, ease,
    onUpdate() {
      const t = o.t;
      cam.z = from.z * Math.pow(to.z / from.z, t); // zoom in log space feels physical
      // keep the screen-space path straight: weight the pan by how far the zoom has progressed
      const k = Math.abs(Math.log(to.z / from.z)) < 1e-3 ? t : (1 / from.z - 1 / cam.z) / (1 / from.z - 1 / to.z);
      cam.cx = from.cx + (to.cx - from.cx) * k;
      cam.cy = from.cy + (to.cy - from.cy) * k;
    },
    onComplete() { flying = false; done(); },
  }));
}
function view() {
  const t = performance.now() / 1000;
  look.x += (look.tx - look.x) * 0.04; look.y += (look.ty - look.y) * 0.04;
  const z = cam.z * (reduced ? 1 : 1 + 0.012 * Math.sin(t * 0.32)); // slow breathing
  const vw = innerWidth / z, vh = innerHeight / z;
  let cx = cam.cx + look.x * vw * 0.045, cy = cam.cy + look.y * vh * 0.035;
  cx = Math.min(Math.max(cx, vw / 2), W - vw / 2);
  cy = Math.min(Math.max(cy, vh / 2), H - vh / 2);
  return { cx, cy, z };
}
const toScreen = (v, x, y) => [innerWidth / 2 + (x - v.cx) * v.z, innerHeight / 2 + (y - v.cy) * v.z];
function frame() {
  const v = view();
  for (const s of Object.values(stills)) {
    if (s.el.style.opacity === "0" || (!s.on && !gsap.isTweening(s.el))) { s.el.style.visibility = "hidden"; continue; }
    s.el.style.visibility = "visible";
    const [x, y] = toScreen(v, s.rect.x, s.rect.y);
    s.el.style.width = s.base.width + "px"; s.el.style.height = s.base.height + "px";
    s.el.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${(s.rect.w * v.z) / s.base.width}, ${(s.rect.h * v.z) / s.base.height})`;
  }
  for (const t of tags.values()) {
    let [x, y] = toScreen(v, t.wx, t.wy);
    x = Math.min(Math.max(x, 120), innerWidth - 120); y = Math.min(Math.max(y, 96), innerHeight - 130); // keep off-screen branches reachable
    t.el.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, -50%)`;
  }
  requestAnimationFrame(frame);
}
function showStill(name, on, { delay = 0, duration = 1.0 } = {}) {
  const s = getStill(name);
  if (s.on === on) return s;
  s.on = on;
  s.ready.then(() => gsap.to(s.el, { opacity: on ? 1 : 0, duration: reduced ? 0.01 : duration, delay, ease: "power1.inOut", overwrite: true }));
  return s;
}

// ---------- labels ----------
const tags = new Map();
const labelsEl = $("#labels");
const fmtCHF = (n) => (n < 0 ? "−" : "") + "CHF " + Math.abs(Math.round(n)).toLocaleString("en-US").replace(/,/g, "’");
function tagMeta(n) {
  const r = n.result;
  if (!r || n.status === "pruned") return "";
  const m = r.metrics, h = r.health;
  const cash = m.first_negative_month != null ? `<span class="warn">cash short from month ${m.first_negative_month + 1}</span>` : "cash stays positive";
  return `Health <b>${Math.round(h.score)}</b> · ${cash}`;
}
function syncTags(nodes, current) {
  const keep = new Set();
  for (const n of nodes) {
    if (n.node_id === current) continue;
    if (n.status === "chosen") continue; // the path is in the breadcrumbs; keep the image clean
    keep.add(n.node_id);
    let t = tags.get(n.node_id);
    if (!t) {
      const el = document.createElement("button");
      el.type = "button";
      el.innerHTML = `<span class="card"><span class="name"></span><span class="meta"></span></span><span class="dot"></span>`;
      el.addEventListener("click", () => onTagClick(n.node_id));
      el.style.opacity = 0;
      labelsEl.append(el);
      const [wx, wy] = anchor(n.node_id);
      t = { el, wx, wy };
      tags.set(n.node_id, t);
      gsap.to(el, { opacity: 1, duration: 0.8, delay: 0.25, ease: "power2.out" });
    }
    t.status = n.status;
    t.el.className = `tag ${n.status}`;
    t.el.disabled = !(n.status === "child" || n.status === "sibling");
    t.el.tabIndex = t.el.disabled ? -1 : 0;
    t.el.setAttribute("aria-label", `${n.label}${n.status === "pruned" ? " (not taken)" : ""}`);
    t.el.querySelector(".name").textContent = n.label;
    const mEl = t.el.querySelector(".meta");
    const showMeta = n.status === "child" || n.status === "sibling";
    mEl.innerHTML = showMeta ? tagMeta(n) : "";
    mEl.hidden = !showMeta || !mEl.innerHTML;
  }
  for (const [id, t] of tags) if (!keep.has(id)) {
    tags.delete(id);
    gsap.to(t.el, { opacity: 0, duration: 0.35, onComplete: () => t.el.remove() });
  }
}

// ---------- data ----------
const seen = new Map(); // node_id -> {label, parent_id}: keeps pruned branches drawn after they leave the API response
let path = [];
let data = null;
async function expand(p) {
  const r = await fetch(`${API}/tree/expand`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ path: p }) });
  if (!r.ok) throw new Error(`expand ${r.status}`);
  return r.json();
}
function visibleNodes(d) {
  const nodes = d.nodes.map((n) => ({ ...n }));
  for (const n of nodes) seen.set(n.node_id, { label: n.label, parent_id: n.parent_id });
  const ids = new Set(nodes.map((n) => n.node_id));
  const ancestors = ["0", ...path.slice(0, -1)];
  for (const [id, s] of seen) {
    if (!ids.has(id) && ancestors.includes(s.parent_id)) nodes.push({ node_id: id, parent_id: s.parent_id, label: s.label, status: "pruned" });
  }
  return nodes;
}

// ---------- Lumi + voice ----------
const lumi = createGuide($("#lumi"), { mood: 70 });
let audioUnlocked = false, muted = false, audio = null, speakSeq = 0;
function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  try { const a = new Audio(); a.muted = true; a.play().catch(() => {}); } catch {}
  try { speechSynthesis.speak(new SpeechSynthesisUtterance("")); } catch {}
}
function stopSpeech() {
  speakSeq++;
  if (audio) { audio.pause(); audio = null; }
  try { speechSynthesis.cancel(); } catch {}
  lumi.setTalking(false);
}
async function speak(text) {
  stopSpeech();
  if (muted || !audioUnlocked) return;
  const seq = speakSeq;
  try {
    const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), 9000);
    const r = await fetch(`${API}/voice/tts`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, language: "en" }), signal: ctl.signal });
    clearTimeout(timer);
    if (!r.ok) throw new Error(`tts ${r.status}`);
    const url = URL.createObjectURL(await r.blob());
    if (seq !== speakSeq) return;
    audio = new Audio(url);
    audio.onplay = () => lumi.setTalking(true);
    audio.onended = audio.onpause = () => lumi.setTalking(false);
    await audio.play();
  } catch {
    if (seq !== speakSeq || !("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-GB"; u.rate = 1.02;
    u.onstart = () => lumi.setTalking(true);
    u.onend = () => lumi.setTalking(false);
    speechSynthesis.speak(u);
  }
}
const sayCard = $("#sayCard"), sayText = $("#sayText");
function narrate(text, pointEl) {
  sayText.textContent = text;
  if (sayCard.hidden) { sayCard.hidden = false; gsap.fromTo(sayCard, { opacity: 0, y: 8, scale: 0.98 }, { opacity: 1, y: 0, scale: 1, duration: 0.5, ease: "power3.out" }); }
  else gsap.fromTo(sayText, { opacity: 0 }, { opacity: 1, duration: 0.4 });
  lumi.pointAt(pointEl || null);
  lumi.setPose?.("explaining");
  speak(text);
}
$("#mute").addEventListener("click", (e) => {
  muted = !muted;
  e.currentTarget.setAttribute("aria-pressed", String(muted));
  e.currentTarget.textContent = muted ? "Sound off" : "Sound on";
  if (muted) stopSpeech(); else { unlockAudio(); speak(sayText.textContent); }
});

const listJoin = (a) => a.length <= 1 ? a.join("") : a.slice(0, -1).join(", ") + " or " + a[a.length - 1];
function storyFor(d) {
  const cur = d.nodes.find((n) => n.node_id === d.current);
  const parent = d.nodes.find((n) => n.node_id === cur.parent_id);
  const kids = d.nodes.filter((n) => n.status === "child").map((n) => n.label.replace(/^./, (c) => c.toLowerCase()));
  const m = cur.result.metrics, h = cur.result.health;
  const cash = m.first_negative_month != null
    ? `In the median path her cash runs short from month ${m.first_negative_month + 1}.`
    : "In the median path her cash never runs out.";
  if (d.current === "0") {
    return `This is Alexia today: ${cur.description.replace(/\.$/, "")}. Her health score is ${Math.round(h.score)} out of 100. ${cash} Three paths grow from here: ${listJoin(kids)}. Choose one and I'll show you what it changes.`;
  }
  const change = (cur.changes && cur.changes[0]) || cur.description;
  const dh = cur.delta_vs_parent?.health_score;
  const delta = dh == null ? "" : ` That is ${Math.abs(dh).toFixed(1)} points ${dh >= 0 ? "higher" : "lower"} than the branch it grows from.`;
  const next = kids.length ? ` From here: ${listJoin(kids)}.` : " This is the end of this branch; open the report for the details.";
  return `${cur.label}. ${change.replace(/\.$/, "")}. Health ${Math.round(h.score)} out of 100.${delta} ${cash}${next} The other branches stay in grey so you can compare.`;
}

// ---------- report ----------
function bandSVG(b) {
  const p10 = b.p10, p50 = b.p50, p90 = b.p90, n = p50.length;
  const all = [...p10, ...p90, 0]; const lo = Math.min(...all), hi = Math.max(...all);
  const X = (i) => (i / (n - 1)) * 360, Y = (v) => 110 - ((v - lo) / (hi - lo || 1)) * 100;
  const line = (arr) => arr.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  const area = `${line(p90)} ${p10.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).reverse().join(" ")}`;
  return `<svg class="band" viewBox="0 0 360 120" preserveAspectRatio="none" role="img" aria-label="Net worth, 10th to 90th percentile over 10 years">
    <line x1="0" x2="360" y1="${Y(0)}" y2="${Y(0)}" stroke="#c9ccc5" stroke-dasharray="3 4"/>
    <polygon points="${area}" fill="#8fb56a" fill-opacity="0.28"/>
    <polyline points="${line(p50)}" fill="none" stroke="#3e6b3a" stroke-width="1.8" vector-effect="non-scaling-stroke"/></svg>`;
}
function renderReport(d) {
  const cur = d.nodes.find((n) => n.node_id === d.current), r = cur.result, m = r.metrics, h = r.health;
  const sens = (r.sensitivity || [])[0];
  const passed = (r.checks || []).filter((c) => c.passed).length;
  const goals = Object.entries(m.goal_probability || {}).map(([k, v]) => `<dt>${k}</dt><dd>${Math.round(v * 100)}%</dd>`).join("");
  $("#reportBody").innerHTML = `
    <div class="kicker">${cur.node_id === "0" ? "Today" : "Branch " + cur.node_id}</div>
    <h2>${cur.label}</h2>
    <p class="desc">${cur.description || ""}</p>
    <div class="score"><b>${Math.round(h.score)}</b><span>health score / 100 · ${h.level}</span></div>
    <dl>
      <dt>Net worth in 10 years (median)</dt><dd>${fmtCHF(m.final_net_worth_p50)}</dd>
      <dt>Range, 10th–90th percentile</dt><dd>${fmtCHF(m.final_net_worth_p10)} – ${fmtCHF(m.final_net_worth_p90)}</dd>
      <dt>Lowest cash</dt><dd class="${m.min_cash < 0 ? "warn" : ""}">${fmtCHF(m.min_cash)}</dd>
      <dt>Cash runs short</dt><dd class="${m.first_negative_month != null ? "warn" : ""}">${m.first_negative_month != null ? "month " + (m.first_negative_month + 1) : "never"}</dd>
      <dt>Futures where cash runs out</dt><dd>${Math.round(m.shortfall_probability * 100)}%</dd>
      ${goals}
    </dl>
    <h3>Net worth, ${r.n_paths.toLocaleString("en-US")} simulated futures</h3>
    ${r.bands?.net_worth ? bandSVG(r.bands.net_worth) : ""}
    <p class="note">Band = 10th to 90th percentile; line = median. Uncertainty, not a forecast.</p>
    ${sens ? `<h3>Assumption that matters most</h3><p class="note"><b>${sens.label}</b> (${sens.base_value} ${sens.unit}): moving it from ${sens.low_value} to ${sens.high_value} shifts the 10-year net worth by ${fmtCHF(sens.delta_final_net_worth)}.</p>` : ""}
    ${cur.changes?.length ? `<h3>What this choice changes</h3><ul>${cur.changes.map((c) => `<li>${c}</li>`).join("")}</ul>` : ""}
    <h3>Checks</h3><p class="note">${passed} of ${(r.checks || []).length} accounting checks passed · engine ${r.engine_version} · seed ${r.seed}</p>`;
}
function openReport() { const el = $("#report"); el.hidden = false; gsap.fromTo(el, { opacity: 0, x: 24 }, { opacity: 1, x: 0, duration: 0.45, ease: "power3.out" }); }
function closeReport() { const el = $("#report"); gsap.to(el, { opacity: 0, x: 24, duration: 0.25, onComplete: () => (el.hidden = true) }); }
$("#reportBtn").addEventListener("click", () => ($("#report").hidden ? openReport() : closeReport()));
$("#reportClose").addEventListener("click", closeReport);

// ---------- navigation ----------
let busy = false;
function crumbs(d) {
  const byId = new Map(d.nodes.map((n) => [n.node_id, n]));
  $("#crumbs").innerHTML = d.path.map((id) => `<span>${byId.get(id)?.label ?? id}</span>`).join("");
}
async function go(newPath) {
  if (busy) return;
  busy = true;
  unlockAudio();
  stopSpeech();
  const loading = setTimeout(() => ($("#loading").hidden = false), 350);
  let d;
  try { d = await expand(newPath); }
  catch (e) { clearTimeout(loading); $("#loading").hidden = true; busy = false; narrate("I can't reach the engine right now. Is the API running?"); return; }
  clearTimeout(loading); $("#loading").hidden = true;
  const goingDeeper = newPath.length > path.length;
  path = newPath; data = d;
  const current = d.current;

  // stills on the chosen path, deeper ones fade in as the camera arrives
  const want = new Set(["master"]);
  for (const id of d.path) { const s = stillFor(id); if (s) want.add(s); }
  for (const name of Object.keys(meta)) if (name !== "hot") {
    if (want.has(name)) { const s = showStill(name, true, { delay: goingDeeper ? 0.7 : 0, duration: 1.1 }); await s.ready; }
    else if (stills[name]?.on) showStill(name, false, { duration: 0.8 });
  }
  // grey every sibling and pruned branch on every visible still
  const nodes = visibleNodes(d);
  const grey = new Set(nodes.filter((n) => n.status === "sibling" || n.status === "pruned").flatMap((n) => codes(n.node_id)));
  for (const s of Object.values(stills)) if (s.on) paintGrey(s, grey);

  syncTags(nodes, current);
  crumbs(d);
  $("#back").hidden = path.length === 0;
  $("#reportBtn").hidden = false;
  renderReport(d);
  if (!$("#report").hidden) openReport();
  const cur = d.nodes.find((n) => n.node_id === current);
  lumi.setMood(cur.result.health.score);
  const fly = camTo(viewRect(current), { duration: goingDeeper ? 2.0 : 1.6 });
  setTimeout(() => narrate(storyFor(d)), goingDeeper ? 900 : 600);
  await fly;
  busy = false;
}
function onTagClick(id) {
  const t = tags.get(id);
  if (!t || busy) return;
  if (t.status === "child") go([...path, id]);
  else if (t.status === "sibling") go([...path.slice(0, -1), id]); // switch sideways, same level
}
function back() { if (path.length && !busy) go(path.slice(0, -1)); }
$("#back").addEventListener("click", back);
addEventListener("keydown", (e) => {
  if (e.target.closest("input")) return;
  if (e.key === "Escape" || e.key === "Backspace") { if (!$("#report").hidden) closeReport(); else back(); }
});
let wheelAcc = 0, wheelT = 0;
addEventListener("wheel", (e) => {
  if (e.target.closest(".report")) return;
  if (!started) { begin(); return; }
  const now = performance.now();
  if (now - wheelT > 400) wheelAcc = 0;
  wheelT = now; wheelAcc += e.deltaY;
  if (wheelAcc < -160) { wheelAcc = 0; back(); } // pull back = one level up, never further
}, { passive: true });
addEventListener("pointermove", (e) => {
  if (e.pointerType !== "mouse") return;
  look.tx = (e.clientX / innerWidth - 0.5) * 2;
  look.ty = (e.clientY / innerHeight - 0.5) * 2;
});

// ---------- ask (type or speak) ----------
$("#ask").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#askInput").value.trim();
  if (!q || !data) return;
  unlockAudio();
  $("#askInput").value = "";
  narrate("Let me check the numbers…");
  try {
    const r = await fetch(`${API}/agent/ask`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question: q, context: { path, node_id: data.current, language: "en" } }) });
    const out = await r.json();
    narrate(out.answer || "I couldn't answer that one.");
  } catch { narrate("I can't reach the engine right now."); }
});
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
$("#micBtn").addEventListener("click", (e) => {
  if (!SR) { narrate("Voice input needs Chrome or Edge. You can type instead."); return; }
  const btn = e.currentTarget, rec = new SR();
  rec.lang = "en-US"; rec.interimResults = true;
  btn.classList.add("rec"); stopSpeech();
  rec.onresult = (ev) => { $("#askInput").value = [...ev.results].map((r) => r[0].transcript).join(""); };
  rec.onend = () => { btn.classList.remove("rec"); if ($("#askInput").value.trim()) $("#ask").requestSubmit(); };
  rec.start();
});

// ---------- intro: from the roots up to the whole tree ----------
let started = false;
const rootsRect = rectOf("roots");
showStill("master", true, { duration: 0.01 });
showStill("roots", true, { duration: 0.01 });
cam.cx = rootsRect.x + rootsRect.w / 2; cam.cy = rootsRect.y + rootsRect.h / 2; cam.z = fitZ(rootsRect);
requestAnimationFrame(frame);
await getStill("roots").ready;
gsap.from(".intro > *", { opacity: 0, y: 16, duration: 1, stagger: 0.12, ease: "power3.out" });
const first = expand([]).catch(() => null); // warm the engine while the intro plays
for (const n of Object.keys(meta)) if (n !== "hot") getStill(n); // preload every still (3 MB)

async function begin() {
  if (started) return;
  started = true;
  unlockAudio();
  gsap.to(".intro", { opacity: 0, y: -12, duration: 0.6, ease: "power2.in", onComplete: () => $("#intro").remove() });
  showStill("roots", false, { delay: 0.5, duration: 1.4 });
  await camTo(viewRect("0"), { duration: 2.8, ease: "power2.inOut" });
  $("#ask").hidden = false;
  gsap.from("#ask", { opacity: 0, y: 12, duration: 0.6, ease: "power3.out" });
  await first;
  go([]);
}
$("#begin").addEventListener("click", begin);
addEventListener("resize", () => { if (data) camTo(viewRect(data.current), { duration: 0.01 }); });
