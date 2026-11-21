// Lumi, the guide: a soft glowing orb that floats next to the tree and explains it.
// Framework-free ES module. Use it from React with a ref:
//
//   import { createGuide } from "../assets/character/guide/guide.js";
//   import "../assets/character/guide/guide.css";
//   const lumi = createGuide(divRef.current, { health: "healthy" });
//   lumi.setHealth("fair");        // "healthy" | "fair" | "weak"  (health of the selected node)
//   lumi.setPose("explaining");    // "idle" | "explaining"        (leans and looks right, sparkles)
//   lumi.setTalking(true);         // mouth moves while audio plays
//   lumi.moveTo(x, y);             // glide (px, relative to the element's offset parent)
//   lumi.destroy();
//
// guideSVG({ health, pose }) returns static SVG markup (used to export the state images).

export const HEALTHS = ["healthy", "fair", "weak"];
export const POSES = ["idle", "explaining"];

const INK = "#1F2B4D";
const BLUSH = "#F6A5C0";

// Hue and saturation of the orb per health, plus how the face and body read.
const HEALTH = {
  healthy: { h: 150, s: 56, eye: 11, mouth: "smile", drop: 0, squash: [1, 1], halo: 1, blush: 0.6 },
  fair: { h: 44, s: 72, eye: 9.5, mouth: "flat", drop: 3, squash: [1.02, 0.97], halo: 0.8, blush: 0.3 },
  weak: { h: 28, s: 14, eye: 7, mouth: "worried", drop: 9, squash: [1.07, 0.91], halo: 0.55, blush: 0.12 },
};

const MOUTH = {
  smile: "M-7,-1.5 Q0,7.5 7,-1.5 Q0,2.5 -7,-1.5 Z",
  flat: "M-5,0.6 Q0,2 5,0.6 Q0,1.2 -5,0.6 Z",
  worried: "M-6,3 Q0,-2.5 6,3 Q0,0.8 -6,3 Z",
  open: "M-6.5,-2 Q0,-3.2 6.5,-2 Q6.5,7 0,8.5 Q-6.5,7 -6.5,-2 Z",
};

// Geometry, in a 200 x 240 viewBox
const CX = 100;
const CY = 116;
const R = 60;
const BASE = CY + R; // bottom of the orb, anchor for squash and tilt

let uid = 0;
const hsl = (h, s, l, a = 1) => `hsla(${h}, ${s}%, ${l}%, ${a})`;

function star(x, y, size, fill) {
  const s = size;
  return `<path d="M${x},${y - s} Q${x + s * 0.15},${y - s * 0.15} ${x + s},${y} Q${x + s * 0.15},${y + s * 0.15} ${x},${y + s} Q${x - s * 0.15},${y + s * 0.15} ${x - s},${y} Q${x - s * 0.15},${y - s * 0.15} ${x},${y - s} Z" fill="${fill}"/>`;
}

export function guideSVG({ health = "healthy", pose = "idle", talking = false, id } = {}) {
  const c = HEALTH[health] ?? HEALTH.healthy;
  const k = id ?? `lumi${++uid}`;
  const { h, s } = c;
  const explaining = pose === "explaining";
  const [sx, sy] = c.squash;
  const tilt = explaining ? 9 : 0;
  const gaze = explaining ? [4.5, -1.5] : [0, health === "weak" ? 1.5 : 0];
  const eyeH = explaining ? c.eye + 1 : c.eye;
  const eyeW = 6.5;
  const mouth = explaining || talking ? MOUTH.open : MOUTH[c.mouth];

  const eye = (x) =>
    `<g class="g-eye"><rect x="${x - eyeW / 2}" y="${-eyeH / 2}" width="${eyeW}" height="${eyeH}" rx="${eyeW / 2}" fill="${INK}"/>` +
    `<circle cx="${x + 1.1}" cy="${-eyeH / 2 + 2.6}" r="1.35" fill="#fff"/></g>`;

  const sparks = explaining
    ? `<g class="g-sparks">${star(176, 84, 7, hsl(h, s + 10, 62))}${star(190, 62, 4.5, hsl(h, s + 10, 70))}${star(164, 58, 3.5, hsl(h, s + 10, 74))}</g>`
    : "";

  return `<svg class="guide-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" role="img" aria-label="Lumi, your guide (${health}, ${pose})">
<defs>
  <radialGradient id="${k}-halo">
    <stop offset="0" stop-color="${hsl(h, s + 10, 78, 0.55 * c.halo)}"/>
    <stop offset=".42" stop-color="${hsl(h, s + 10, 76, 0.18 * c.halo)}"/>
    <stop offset=".68" stop-color="${hsl(h, s, 76, 0)}"/>
  </radialGradient>
  <radialGradient id="${k}-body" cx="50%" cy="50%" r="50%">
    <stop offset="0" stop-color="${hsl(h, s, 95)}"/>
    <stop offset=".6" stop-color="${hsl(h, s, 87)}"/>
    <stop offset="1" stop-color="${hsl(h, s * 0.8, 73)}"/>
  </radialGradient>
  <radialGradient id="${k}-shade" cx="36%" cy="30%" r="78%">
    <stop offset=".55" stop-color="${hsl(h, 45, 46, 0)}"/>
    <stop offset="1" stop-color="${hsl(h, 45, 46, 0.4)}"/>
  </radialGradient>
  <radialGradient id="${k}-shine" cx="33%" cy="27%" r="50%">
    <stop offset="0" stop-color="#fff" stop-opacity="1"/>
    <stop offset=".34" stop-color="#fff" stop-opacity=".85"/>
    <stop offset=".9" stop-color="#fff" stop-opacity="0"/>
  </radialGradient>
</defs>
<ellipse class="g-shadow" cx="${CX}" cy="206" rx="${42 + c.drop}" ry="6.5" fill="${INK}" opacity=".12"/>
<g class="g-float">
 <g class="g-pose" transform="translate(0 ${c.drop}) rotate(${tilt} ${CX} ${BASE}) translate(${CX} ${BASE}) scale(${sx} ${sy}) translate(${-CX} ${-BASE})">
  <circle class="g-halo" cx="${CX}" cy="${CY}" r="${R * 1.65}" fill="url(#${k}-halo)"/>
  <g class="g-jelly">
   <circle cx="${CX}" cy="${CY}" r="${R}" fill="url(#${k}-body)"/>
   <circle cx="${CX}" cy="${CY}" r="${R}" fill="url(#${k}-shade)"/>
   <circle cx="${CX}" cy="${CY}" r="${R}" fill="url(#${k}-shine)"/>
   <g class="g-face" transform="translate(${CX} ${CY + 10}) scale(1.3)">
    <ellipse cx="-23" cy="10" rx="7" ry="3.8" fill="${BLUSH}" opacity="${c.blush}"/>
    <ellipse cx="23" cy="10" rx="7" ry="3.8" fill="${BLUSH}" opacity="${c.blush}"/>
    <g class="g-eyes" transform="translate(${gaze[0]} ${gaze[1]})">${eye(-12)}${eye(12)}</g>
    <g transform="translate(${gaze[0] * 0.6} 13)"><path class="g-mouth" d="${mouth}" fill="${INK}" stroke="${INK}" stroke-width="1.1" stroke-linejoin="round"/></g>
   </g>
  </g>
 </g>
 ${sparks}
</g>
</svg>`;
}

export function createGuide(el, { health = "healthy", pose = "idle" } = {}) {
  const state = { health, pose, talking: false };
  const id = `lumi${++uid}`;
  el.classList.add("guide");
  const t0 = performance.now();
  let moveTimer = 0;

  // Each change renders a new layer and cross-fades it over the old one. Animations are kept in
  // phase with a negative delay so the float never jumps.
  function render() {
    const layer = document.createElement("div");
    layer.className = "guide-layer is-entering";
    layer.style.setProperty("--phase", `${-((performance.now() - t0) / 1000)}s`);
    layer.innerHTML = guideSVG({ ...state, id: `${id}-${Date.now()}` });
    if (state.talking) layer.classList.add("is-talking");
    el.appendChild(layer);
    requestAnimationFrame(() => layer.classList.remove("is-entering"));
    for (const old of el.querySelectorAll(".guide-layer:not(:last-child)")) {
      old.classList.add("is-leaving");
      setTimeout(() => old.remove(), 450);
    }
  }
  render();

  return {
    get state() {
      return { ...state };
    },
    setHealth(h) {
      if (!HEALTH[h] || h === state.health) return;
      state.health = h;
      render();
    },
    setPose(p) {
      if (!POSES.includes(p) || p === state.pose) return;
      state.pose = p;
      render();
    },
    setTalking(on) {
      state.talking = !!on;
      el.querySelector(".guide-layer:last-child")?.classList.toggle("is-talking", state.talking);
    },
    moveTo(x, y) {
      el.classList.add("is-moving");
      el.style.transform = `translate(${x}px, ${y}px)`;
      clearTimeout(moveTimer);
      moveTimer = setTimeout(() => el.classList.remove("is-moving"), 900);
    },
    destroy() {
      clearTimeout(moveTimer);
      el.replaceChildren();
      el.classList.remove("guide", "is-moving");
    },
  };
}
