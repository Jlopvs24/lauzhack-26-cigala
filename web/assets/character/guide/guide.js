// Lumi, the guide: a soft glowing orb that floats next to the tree and explains it.
// It never recommends or decides. Framework-free ES module; use it from React with a ref:
//
//   import { createGuide } from "../assets/character/guide/guide.js";
//   import "../assets/character/guide/guide.css";
//   const lumi = createGuide(divRef.current, { mood: "healthy", onTap: () => openChat() });
//   lumi.setMood(node.health.score);  // 0-100 score, engine level ("strong" | "ok" | "fragile")
//                                     // or "healthy" | "fair" | "weak"
//   await lumi.say("Cash runs out in month 7 in the median path.");  // bubble + talking mouth
//   lumi.pointAt(leafElement);        // look, lean and sparkle toward an Element or {x, y}
//   lumi.pointAt(null);               //   ({x, y} in viewport px, as getBoundingClientRect)
//   lumi.moveTo(x, y);                // glide (px, relative to where the element sits)
//   lumi.setTalking(true);            // mouth moves while your own audio plays
//   lumi.react("happy");              // short reaction: "happy" | "curious" | "surprised"
//   lumi.destroy();
//
// Alive on its own: it bobs, blinks and glances around; watches the cursor and slightly dodges
// it when it gets close; smiles on hover; on click (or Enter) it spins a full turn (the face
// slides round the sphere), hops with a crouch first and sends a ripple of light; it dozes off
// when nobody moves for a while. With prefers-reduced-motion it only changes face and colour.
//
// guideSVG({ health, pose }) returns static SVG markup (used to export the state images).

export const HEALTHS = ["healthy", "fair", "weak"];
export const POSES = ["idle", "explaining"];

const INK = "#1F2B4D";
const BLUSH = "#F6A5C0";

// Per health: hue/saturation of the orb, glow, face and how heavy it sits.
// curve: mouth curvature (+ smile, - worried).
const HEALTH = {
  healthy: { h: 150, s: 56, halo: 1, blush: 0.6, eye: 11, curve: 4, drop: 0, flat: 0, bob: 1 },
  fair: { h: 44, s: 72, halo: 0.8, blush: 0.3, eye: 9.5, curve: 0.8, drop: 3, flat: 0.4, bob: 0.8 },
  weak: { h: 28, s: 14, halo: 0.55, blush: 0.12, eye: 7, curve: -3, drop: 9, flat: 1.2, bob: 0.5 },
};

// Engine health levels (core/analysis.py): strong >= 70, ok >= 40, else fragile.
export function moodToHealth(m) {
  if (typeof m === "number" && Number.isFinite(m)) return m >= 70 ? "healthy" : m >= 40 ? "fair" : "weak";
  return { strong: "healthy", ok: "fair", fragile: "weak" }[m] ?? (HEALTH[m] ? m : "healthy");
}

// Geometry, in a 200 x 240 viewBox
const CX = 100;
const CY = 116;
const R = 60;
const BASE = CY + R; // bottom of the orb: anchor for squash and tilt
const FACE = 1.3;
const EYE_X = 12;
const EYE_W = 6.5;

const hsl = (h, s, l, a = 1) => `hsla(${h.toFixed(1)}, ${s.toFixed(1)}%, ${l}%, ${a.toFixed(3)})`;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const rand = (a, b) => a + Math.random() * (b - a);

// Gradient stops, shared by the static markup and the live loop: fn(hue, sat, halo) -> colour
const STOPS = {
  halo: [
    [0, (h, s, g) => hsl(h, s + 10, 78, 0.55 * g)],
    [0.42, (h, s, g) => hsl(h, s + 10, 76, 0.18 * g)],
    [0.68, (h, s) => hsl(h, s + 10, 76, 0)],
  ],
  body: [
    [0, (h, s) => hsl(h, s, 95)],
    [0.6, (h, s) => hsl(h, s, 87)],
    [1, (h, s) => hsl(h, s * 0.8, 73)],
  ],
  shade: [
    [0.55, (h) => hsl(h, 45, 46, 0)],
    [1, (h) => hsl(h, 45, 46, 0.4)],
  ],
};
const GRAD_POS = { halo: "", body: ' cx="50%" cy="50%" r="50%"', shade: ' cx="36%" cy="30%" r="78%"' };

// Lens-shaped mouth: corners at (+-w, 0); curve bends it, open separates the lips.
const mouthPath = (w, curve, open) =>
  `M${-w},0 Q0,${(curve - open).toFixed(2)} ${w},0 Q0,${(curve + open).toFixed(2)} ${-w},0 Z`;

function star(x, y, s) {
  return `<path d="M${x},${y - s} Q${x + s * 0.15},${y - s * 0.15} ${x + s},${y} Q${x + s * 0.15},${y + s * 0.15} ${x},${y + s} Q${x - s * 0.15},${y + s * 0.15} ${x - s},${y} Q${x - s * 0.15},${y - s * 0.15} ${x},${y - s} Z"/>`;
}

// ------------------------------------------------------------------ static markup

/** Full SVG for one state. The live guide uses the same markup and then drives it every frame. */
export function guideSVG({ health = "healthy", pose = "idle", talking = false, id = "lumi" } = {}) {
  const hname = moodToHealth(health);
  const c = HEALTH[hname];
  const explaining = pose === "explaining";
  const tilt = explaining ? 9 : 0;
  const gaze = explaining ? [4.5, -1.5] : [0, hname === "weak" ? 1.5 : 0];
  const eyeH = explaining ? c.eye + 1 : c.eye;
  const open = explaining || talking ? 4.5 : 1;
  const curve = explaining || talking ? 2 : c.curve;
  const sq = c.flat * 0.06;

  const grad = (name) =>
    `<radialGradient id="${id}-${name}"${GRAD_POS[name]}>` +
    STOPS[name].map(([o, f]) => `<stop offset="${o}" stop-color="${f(c.h, c.s, c.halo)}"/>`).join("") +
    `</radialGradient>`;
  const eye = (side) => {
    const x = side * EYE_X;
    return (
      `<g class="g-eye">` +
      `<rect class="g-pupil" x="${x - EYE_W / 2}" y="${-eyeH / 2}" width="${EYE_W}" height="${eyeH}" rx="${EYE_W / 2}" fill="${INK}"/>` +
      `<path class="g-arc" d="M${x - 4.5},1.5 Q${x},-5 ${x + 4.5},1.5" fill="none" stroke="${INK}" stroke-width="3" stroke-linecap="round" opacity="0"/>` +
      `<circle class="g-glint" cx="${x + 1.1}" cy="${-eyeH / 2 + 2.6}" r="1.35" fill="#fff"/></g>`
    );
  };

  return `<svg class="guide-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" role="img" aria-label="Lumi, your guide">
<defs>${grad("halo")}${grad("body")}${grad("shade")}
  <radialGradient id="${id}-shine" cx="33%" cy="27%" r="50%"><stop offset="0" stop-color="#fff"/><stop offset=".34" stop-color="#fff" stop-opacity=".85"/><stop offset=".9" stop-color="#fff" stop-opacity="0"/></radialGradient>
</defs>
<ellipse class="g-shadow" cx="${CX}" cy="206" rx="${42 + c.drop}" ry="6.5" fill="${INK}" opacity=".12"/>
<g class="g-pose" transform="translate(0 ${c.drop}) rotate(${tilt} ${CX} ${BASE}) translate(${CX} ${BASE}) scale(${1 + sq} ${1 - sq}) translate(${-CX} ${-BASE})">
 <circle class="g-halo" cx="${CX}" cy="${CY}" r="${R * 1.65}" fill="url(#${id}-halo)"/>
 <circle class="g-ring" cx="${CX}" cy="${CY}" r="${R}" fill="none" stroke-width="3" opacity="0"/>
 <circle cx="${CX}" cy="${CY}" r="${R}" fill="url(#${id}-body)"/>
 <circle cx="${CX}" cy="${CY}" r="${R}" fill="url(#${id}-shade)"/>
 <circle cx="${CX}" cy="${CY}" r="${R}" fill="url(#${id}-shine)"/>
 <g class="g-face" transform="translate(${CX} ${CY + 10}) scale(${FACE})">
  <ellipse class="g-blush" cx="-23" cy="10" rx="7" ry="3.8" fill="${BLUSH}" opacity="${c.blush}"/>
  <ellipse class="g-blush" cx="23" cy="10" rx="7" ry="3.8" fill="${BLUSH}" opacity="${c.blush}"/>
  <g class="g-eyes" transform="translate(${gaze[0]} ${gaze[1]})">${eye(-1)}${eye(1)}</g>
  <g class="g-mouth-pos" transform="translate(${gaze[0] * 0.6} 13)"><path class="g-mouth" d="${mouthPath(explaining ? 6 : 6.5, curve, open)}" fill="${INK}" stroke="${INK}" stroke-width="1.1" stroke-linejoin="round"/></g>
 </g>
</g>
<g class="g-sparks" fill="${hsl(c.h, c.s + 10, 66)}" opacity="${explaining ? 1 : 0}">${star(176, 84, 7)}${star(190, 62, 4.5)}${star(164, 58, 3.5)}</g>
</svg>`;
}

// ------------------------------------------------------------------ live guide

let uid = 0;

export function createGuide(el, { mood, health = "healthy", pose = "idle", onTap } = {}) {
  if (mood !== undefined) health = mood;
  health = moodToHealth(health);
  const id = `lumi${++uid}`;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.classList.add("guide");
  el.tabIndex = 0;
  el.setAttribute("role", "button");
  el.setAttribute("aria-label", "Lumi, your guide");
  el.innerHTML =
    `<div class="guide-nudge">${guideSVG({ health, pose, id })}</div>` +
    `<div class="guide-say" role="status" aria-live="polite" hidden></div>`;

  const q = (sel) => el.querySelector(sel);
  const qa = (sel) => [...el.querySelectorAll(sel)];
  const dom = {
    svg: q(".guide-svg"),
    nudge: q(".guide-nudge"),
    bubble: q(".guide-say"),
    pose: q(".g-pose"),
    shadow: q(".g-shadow"),
    halo: q(".g-halo"),
    ring: q(".g-ring"),
    face: q(".g-face"),
    eyes: q(".g-eyes"),
    pupils: qa(".g-pupil"),
    arcs: qa(".g-arc"),
    glints: qa(".g-glint"),
    mouthPos: q(".g-mouth-pos"),
    mouth: q(".g-mouth"),
    blush: qa(".g-blush"),
    sparks: q(".g-sparks"),
    stops: Object.fromEntries(Object.keys(STOPS).map((k) => [k, qa(`#${id}-${k} stop`)])),
  };

  const target = { health, pose, talking: false };
  const cur = { ...HEALTH[health] }; // health params, eased toward the target every frame
  const face = { eyeL: cur.eye, eyeR: cur.eye, happy: 0, curve: cur.curve, open: 1, tilt: 0, blush: cur.blush, sparks: pose === "explaining" ? 1 : 0 };
  const now0 = performance.now();
  const s = {
    t0: now0,
    last: now0,
    y: 0, vy: 0, // hop
    sq: 0, sqv: 0, // jelly: + squash, - stretch
    lean: 0,
    spin: 0, spinTo: 0,
    gx: 0, gy: 0, glance: [0, 0], nextGlance: 0,
    nextBlink: now0 + rand(1500, 4000), blinkAt: -1e9,
    flash: null, flashUntil: 0,
    ringAt: -1e9,
    mouse: { x: -1e4, y: -1e4, at: -1e9 },
    lastInput: now0,
    noticeUntil: 0,
    talk: 0,
    colorKey: "",
    pos: { x: 0, y: 0 },
    dx: 0, dy: 0, // dodge offset, px
    point: null, // Element or {x, y} it is pointing at
    sayTimer: 0, sayDone: null,
  };

  function react(emo, ms = 1100) {
    s.flash = emo;
    s.flashUntil = performance.now() + ms;
  }

  // orb centre and radius in viewport px (without the dodge offset, so dodging never feeds back)
  const center = () => {
    const b = dom.svg.getBoundingClientRect();
    return { x: b.left + (b.width * CX) / 200 - s.dx, y: b.top + (b.height * CY) / 240 - s.dy, r: (b.width * R) / 200 };
  };

  // -------------------------------------------------------------- input
  const onMove = (e) => {
    const now = performance.now();
    if (now - s.mouse.at > 4000) s.noticeUntil = now + 1400; // you came back: it notices
    if (now - s.lastInput > 25000) react("surprised", 700); // woken up
    s.mouse = { x: e.clientX, y: e.clientY, at: now };
    s.lastInput = now;
  };
  const onTapEvent = (e) => {
    if (e.type === "keydown" && e.key !== "Enter" && e.key !== " ") return;
    if (e.type === "keydown") e.preventDefault();
    s.lastInput = performance.now();
    tap();
    onTap?.();
  };
  const onEnter = () => {
    react("happy", 1000);
    s.sqv += 3;
  };
  addEventListener("pointermove", onMove, { passive: true });
  el.addEventListener("pointerdown", onTapEvent);
  el.addEventListener("keydown", onTapEvent);
  el.addEventListener("pointerenter", onEnter);

  function tap() {
    react("happy", 1300);
    s.ringAt = performance.now();
    if (reduced) return;
    s.spinTo += Math.PI * 2;
    // crouch, then jump: the anticipation sells the weight
    s.sqv += 5;
    setTimeout(() => {
      s.vy = -340;
      s.sqv -= 9;
    }, 110);
  }

  // -------------------------------------------------------------- frame
  let raf = 0;
  function frame() {
    const now = performance.now(); // same clock as the input handlers
    const dt = clamp((now - s.last) / 1000, 0, 0.5); // frame-rate independent below
    s.last = now;
    const T = (now - s.t0) / 1000;
    const k = (rate) => 1 - Math.exp(-rate * dt);

    // health eases in: colour, glow, face and weight all drift together
    const H = HEALTH[target.health];
    for (const key in cur) cur[key] = lerp(cur[key], H[key], k(2.5));

    const c = center();
    const md = Math.hypot(s.mouse.x - c.x, s.mouse.y - c.y);
    const recent = now - s.mouse.at < 2500;
    const near = recent ? clamp(1 - md / (c.r * 3.2), 0, 1) : 0;

    // pointing: at an Element (tracked live) or a viewport point
    let pt = null;
    if (s.point instanceof Element) {
      const b = s.point.getBoundingClientRect();
      pt = { x: b.left + b.width / 2, y: b.top + b.height / 2 };
    } else if (s.point) pt = s.point;
    const pdx = pt ? pt.x - c.x : 1;
    const pdy = pt ? pt.y - c.y : -0.35;
    const pd = Math.hypot(pdx, pdy) || 1;
    const explaining = target.pose === "explaining" || !!pt;

    // emotion: a short reaction wins; otherwise dozing, curious about a close cursor, or calm
    let emo = "calm";
    if (s.flash && now < s.flashUntil) emo = s.flash;
    else if (now - s.lastInput > 25000 && !target.talking && !explaining) emo = "sleepy";
    else if (near > 0.15 && !explaining) emo = "curious";

    const F = { eyeL: cur.eye, eyeR: cur.eye, happy: 0, curve: cur.curve, open: 1, tilt: 0, blush: cur.blush, bob: cur.bob };
    if (explaining) Object.assign(F, { tilt: 9 * Math.sign(pdx || 1), eyeL: cur.eye + 1, eyeR: cur.eye + 1 });
    if (emo === "happy") Object.assign(F, { happy: 1, curve: 5.5, open: 2.4, blush: Math.max(0.7, cur.blush) });
    if (emo === "curious") Object.assign(F, { eyeL: cur.eye + 2, eyeR: cur.eye - 1, tilt: 10, open: 1.6, curve: Math.max(0.5, cur.curve * 0.5) });
    if (emo === "surprised") Object.assign(F, { eyeL: cur.eye + 3, eyeR: cur.eye + 3, curve: 0, open: 3.6 });
    if (emo === "sleepy") Object.assign(F, { eyeL: 1.6, eyeR: 1.6, tilt: 5, open: 0.6, curve: 1, bob: 0.4 });
    for (const key of ["eyeL", "eyeR", "happy", "curve", "open", "tilt", "blush"]) face[key] = lerp(face[key], F[key], k(10));
    face.sparks = lerp(face.sparks, explaining ? 1 : 0, k(6));

    // talking: lips open and close on a syllable-like rhythm (two unrelated waves)
    const flap = target.talking ? 0.3 + 0.7 * Math.abs(Math.sin(T * 12.5) * Math.sin(T * 6.9 + 0.6)) : 0;
    s.talk = lerp(s.talk, flap, k(25));

    // gaze: what it points at; else the cursor when close (or just came back); else glances
    let gx, gy;
    if (explaining) [gx, gy] = [pdx / pd, pdy / pd];
    else if (emo === "sleepy") [gx, gy] = [0, 0.4];
    else if (now < s.noticeUntil || near > 0) {
      const m = Math.min(1, md / (c.r * 2.2));
      [gx, gy] = [((s.mouse.x - c.x) / (md || 1)) * m, ((s.mouse.y - c.y) / (md || 1)) * m];
    } else {
      if (now > s.nextGlance) {
        s.glance = Math.random() < 0.5 ? [0, 0] : [rand(-0.8, 0.8), rand(-0.5, 0.5)];
        s.nextGlance = now + rand(1800, 4500);
      }
      [gx, gy] = s.glance;
    }
    s.gx = lerp(s.gx, gx, k(9));
    s.gy = lerp(s.gy, gy, k(9));

    // blink
    if (now > s.nextBlink) {
      s.blinkAt = now;
      s.nextBlink = now + rand(2800, 6500);
    }
    const bt = (now - s.blinkAt) / 160;
    const blink = bt >= 0 && bt <= 1 ? 1 - 0.9 * Math.sin(Math.PI * bt) : 1;

    // physics: hop under gravity, jelly spring, spin easing, lean from moving
    if (!reduced) {
      for (let left = dt; left > 0; left -= 1 / 120) {
        const h = Math.min(1 / 120, left); // fixed small steps keep the springs stable
        s.vy += 1900 * h;
        s.y += s.vy * h;
        if (s.y > 0) {
          if (s.vy > 120) s.sqv += s.vy / 90; // landing squash
          s.y = 0;
          s.vy = 0;
        }
        s.sqv += (-170 * s.sq - 11 * s.sqv) * h;
        s.sq += s.sqv * h;
      }
      s.spin = lerp(s.spin, s.spinTo, k(4.5));
    }
    s.lean = lerp(s.lean, 0, k(3));

    // dodge: when the cursor gets close it slips a little away from it, then drifts back
    let ddx = 0;
    let ddy = 0;
    const zone = c.r * 2.3;
    if (!reduced && recent && md < zone) {
      const push = (1 - md / zone) * c.r * 0.7;
      ddx = (-(s.mouse.x - c.x) / (md || 1)) * push;
      ddy = (-(s.mouse.y - c.y) / (md || 1)) * push * 0.6;
    }
    const dodging = ddx !== 0 || ddy !== 0;
    s.dx = lerp(s.dx, ddx, k(dodging ? 7 : 2.5));
    s.dy = lerp(s.dy, ddy, k(dodging ? 7 : 2.5));
    dom.nudge.style.transform = `translate(${s.dx.toFixed(1)}px, ${s.dy.toFixed(1)}px)`;

    const bob = reduced ? 0 : (Math.sin(T * 1.7) * 3.4 + Math.sin(T * 0.67 + 1.1) * 1.5) * F.bob;
    const lift = s.y + bob + cur.drop;
    const sq = clamp(s.sq * 0.06 + cur.flat * 0.06, -0.25, 0.3);
    const tilt = face.tilt + s.lean;
    dom.pose.setAttribute(
      "transform",
      `translate(0 ${lift.toFixed(2)}) rotate(${tilt.toFixed(2)} ${CX} ${BASE}) translate(${CX} ${BASE}) scale(${(1 + sq).toFixed(3)} ${(1 - sq).toFixed(3)}) translate(${-CX} ${-BASE})`,
    );
    const air = clamp(1 + (s.y + bob) / 140, 0.55, 1.1);
    dom.shadow.setAttribute("transform", `translate(${CX} 206) scale(${air.toFixed(3)} 1) translate(${-CX} -206)`);
    dom.shadow.setAttribute("opacity", (0.12 * air).toFixed(3));

    // colour: only touch the gradients when it actually changed
    const key = `${cur.h.toFixed(1)}|${cur.s.toFixed(1)}|${cur.halo.toFixed(2)}`;
    if (key !== s.colorKey) {
      s.colorKey = key;
      for (const name in STOPS) STOPS[name].forEach(([, f], i) => dom.stops[name][i].setAttribute("stop-color", f(cur.h, cur.s, cur.halo)));
      dom.sparks.setAttribute("fill", hsl(cur.h, cur.s + 10, 66));
      dom.ring.setAttribute("stroke", hsl(cur.h, cur.s + 15, 70));
    }
    dom.halo.setAttribute("r", (R * 1.65 * (1 + 0.035 * Math.sin(T * 1.3) + 0.05 * s.talk)).toFixed(2));

    // sparkles on the side it points to (drawn at about -35 deg, upper right)
    const ang = (Math.atan2(pdy, pdx) * 180) / Math.PI + 35;
    dom.sparks.setAttribute("opacity", face.sparks.toFixed(3));
    dom.sparks.setAttribute("transform", `rotate(${ang.toFixed(1)} ${CX} ${CY})`);

    // ripple of light on tap
    const rt = (now - s.ringAt) / 650;
    if (rt >= 0 && rt <= 1) {
      dom.ring.setAttribute("r", (R * (1 + 0.6 * (1 - (1 - rt) ** 3))).toFixed(2));
      dom.ring.setAttribute("opacity", (0.7 * (1 - rt)).toFixed(3));
    } else dom.ring.setAttribute("opacity", "0");

    // face: follows the gaze a little, and slides round the sphere while it spins
    const sin = Math.sin(s.spin);
    const cos = Math.cos(s.spin);
    const fx = CX + s.gx * 5 + sin * 34;
    const fy = CY + 10 + s.gy * 4;
    dom.face.setAttribute("transform", `translate(${fx.toFixed(2)} ${fy.toFixed(2)}) scale(${(Math.max(0.02, Math.abs(cos)) * FACE).toFixed(3)} ${FACE})`);
    dom.face.setAttribute("opacity", clamp(cos * 3, 0, 1).toFixed(3));
    dom.eyes.setAttribute("transform", `translate(${(s.gx * 5).toFixed(2)} ${(s.gy * 3.2).toFixed(2)})`);
    [face.eyeL, face.eyeR].forEach((h0, i) => {
      const h = Math.max(1.4, h0 * blink);
      const x = (i ? 1 : -1) * EYE_X;
      const p = dom.pupils[i];
      p.setAttribute("y", (-h / 2).toFixed(2));
      p.setAttribute("height", h.toFixed(2));
      p.setAttribute("rx", (Math.min(EYE_W, h) / 2).toFixed(2));
      p.setAttribute("opacity", (1 - face.happy).toFixed(3));
      dom.arcs[i].setAttribute("opacity", face.happy.toFixed(3));
      dom.glints[i].setAttribute("cx", (x + 1.1).toFixed(2));
      dom.glints[i].setAttribute("cy", (-h / 2 + 2.6).toFixed(2));
      dom.glints[i].setAttribute("r", h > 5 && face.happy < 0.5 ? "1.35" : "0");
    });
    const open = face.open + s.talk * 4.5;
    const curve = face.curve * (1 - s.talk * 0.5);
    dom.mouthPos.setAttribute("transform", `translate(${(s.gx * 2.4).toFixed(2)} ${(13 + s.gy * 1.5).toFixed(2)})`);
    dom.mouth.setAttribute("d", mouthPath(6.5 + s.talk, curve, open));
    for (const b of dom.blush) b.setAttribute("opacity", face.blush.toFixed(3));

    raf = requestAnimationFrame(frame);
  }
  raf = requestAnimationFrame(frame);

  function hideBubble() {
    dom.bubble.hidden = true;
    target.talking = false;
    const done = s.sayDone;
    s.sayDone = null;
    done?.();
  }

  return {
    get state() {
      return { ...target, pointing: !!s.point };
    },
    /** Health of the selected node: 0-100 score, "strong"|"ok"|"fragile" or "healthy"|"fair"|"weak". */
    setMood(m) {
      target.health = moodToHealth(m);
    },
    setHealth(h) {
      target.health = moodToHealth(h);
    },
    setPose(p) {
      if (POSES.includes(p)) target.pose = p;
    },
    /** Speech bubble + talking mouth. Resolves when it hides (after `duration` ms, or a reading-time guess). say("") hides it. */
    say(text, { duration } = {}) {
      clearTimeout(s.sayTimer);
      hideBubble();
      const t = String(text ?? "").trim();
      if (!t) return Promise.resolve();
      dom.bubble.textContent = t;
      dom.bubble.hidden = false;
      target.talking = true;
      s.lastInput = performance.now();
      const ms = duration ?? clamp(t.length * 55, 2200, 12000);
      return new Promise((resolve) => {
        s.sayDone = resolve;
        s.sayTimer = setTimeout(hideBubble, ms);
      });
    },
    /** Look, lean and sparkle toward an Element (tracked live) or a viewport point {x, y}; null stops. */
    pointAt(p) {
      if (p instanceof Element) s.point = p;
      else if (Array.isArray(p)) s.point = { x: p[0], y: p[1] };
      else if (p && Number.isFinite(p.x) && Number.isFinite(p.y)) s.point = { x: p.x, y: p.y };
      else s.point = null;
      s.lastInput = performance.now();
    },
    setTalking(on) {
      target.talking = !!on;
      if (on) s.lastInput = performance.now();
    },
    react,
    tap,
    moveTo(x, y) {
      const dx = x - s.pos.x;
      s.pos = { x, y };
      s.lean = clamp(dx / 30, -12, 12); // leans into the trip
      s.sqv -= 6; // and stretches as it sets off
      s.lastInput = performance.now();
      el.style.transform = `translate(${x}px, ${y}px)`;
    },
    destroy() {
      cancelAnimationFrame(raf);
      clearTimeout(s.sayTimer);
      hideBubble();
      removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerdown", onTapEvent);
      el.removeEventListener("keydown", onTapEvent);
      el.removeEventListener("pointerenter", onEnter);
      el.replaceChildren();
      el.classList.remove("guide");
      el.style.transform = "";
    },
  };
}
