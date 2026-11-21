// The photographic tree: matched 2K stills on one world plane, a camera that flies between their
// rectangles (zoom in log space), feathered greying of sibling/pruned branches from label maps,
// and HTML labels anchored to branch positions. Framework-free; main.jsx drives it.
import gsap from 'gsap';
import { createGeometry, codes as codesOf } from './geometry.js';

const BASE = `${import.meta.env?.BASE_URL || '/'}tree/`;
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

export async function createScene({ world, labels, onTagClick }) {
  const meta = await (await fetch(`${BASE}stills.json`)).json();
  const geo = createGeometry(meta);
  const stills = {};
  const tags = new Map();
  const cam = { cx: geo.W / 2, cy: geo.H / 2, z: 1 };
  const look = { x: 0, y: 0, tx: 0, ty: 0 };
  let raf = 0, alive = true;

  // A still = the photo + a greyscaled copy of it, masked by the union of the branches to grey.
  // Both are plain <img>: decoding is async and greying is a GPU filter + CSS mask (no pixel loops).
  function getStill(name) {
    if (stills[name]) return stills[name];
    const st = meta.stills[name];
    const el = document.createElement('div');
    el.className = name === 'master' ? 'still master' : 'still';
    el.style.zIndex = name === 'master' ? 0 : name.split('_').length;
    const [pw, ph] = st.px || [2752, 1536];
    el.style.width = `${pw}px`; el.style.height = `${ph}px`;
    const base = new Image(), grey = new Image(), dim = new Image();
    base.decoding = grey.decoding = dim.decoding = 'async';
    base.alt = grey.alt = dim.alt = ''; base.draggable = grey.draggable = dim.draggable = false;
    grey.className = 'grey'; dim.className = 'dim';
    base.src = grey.src = dim.src = BASE + st.src;
    el.append(base, grey, dim);
    world.append(el);
    const s = { name, el, base, grey, dim, pw, ph, rect: geo.rectOf(name), on: false, greyKey: '', dimKey: '' };
    s.ready = base.decode().catch(() => new Promise((ok) => { if (base.complete) ok(); else base.onload = base.onerror = ok; }));
    stills[name] = s;
    return s;
  }
  function paintGrey(s, set) {
    const masks = meta.stills[s.name].masks || {};
    const codes = [...set].filter((c) => masks[c]).sort();
    const key = codes.join(',');
    if (s.greyKey === key) return;
    s.greyKey = key;
    if (!codes.length) { s.grey.style.opacity = 0; return; }
    const list = codes.map((c) => `url("${BASE}${masks[c]}")`).join(', ');
    s.grey.style.webkitMaskImage = s.grey.style.maskImage = list;
    if (!reduced()) gsap.fromTo(s.grey, { opacity: 0 }, { opacity: 1, duration: 1.1, ease: 'power2.out', overwrite: true });
    else s.grey.style.opacity = 1;
  }
  // weather: branches whose plan no longer holds lose their light (same masks as the greying)
  function paintDim(s, set) {
    const masks = meta.stills[s.name].masks || {};
    const codes = [...set].filter((c) => masks[c]).sort();
    const key = codes.join(',');
    if (s.dimKey === key) return;
    s.dimKey = key;
    if (codes.length) s.dim.style.webkitMaskImage = s.dim.style.maskImage = codes.map((c) => `url("${BASE}${masks[c]}")`).join(', ');
    gsap.to(s.dim, { opacity: codes.length ? 1 : 0, duration: reduced() ? 0.01 : 1.2, ease: 'power2.out', overwrite: true });
  }
  function release(s) {
    s.base.src = s.grey.src = s.dim.src = '';
    s.el.remove();
    delete stills[s.name];
  }
  function showStill(name, on, { delay = 0, duration = 1.0 } = {}) {
    const s = getStill(name);
    if (s.on === on) return s;
    s.on = on;
    s.ready.then(() => gsap.to(s.el, {
      opacity: on ? 1 : 0, duration: reduced() ? 0.01 : duration, delay, ease: 'power1.inOut', overwrite: true,
      onComplete: () => { if (!s.on && name !== 'master' && stills[name] === s) release(s); }, // free decoded 2K images
    }));
    return s;
  }
  const fetched = new Set();
  function prefetch(names) { // warm the HTTP cache only; decoding happens when the still is shown
    for (const n of names) if (n && meta.stills[n] && !fetched.has(n)) { fetched.add(n); new Image().src = BASE + meta.stills[n].src; }
  }

  // ---------- camera ----------
  let insetRight = 0, insetBottom = 0, currentId = '0';
  const VW = () => Math.max(320, innerWidth - insetRight); // the scene: the window minus the chat panel
  const VH = () => Math.max(320, innerHeight - insetBottom);
  const fitZ = (r) => Math.max(VW() / r.w, VH() / r.h);
  let flight = null; // one camera flight at a time: a new one starts from wherever the camera is now
  function camTo(r, { duration = 1.8, ease = 'power3.inOut' } = {}) {
    flight?.kill(); flight?.vars?.onComplete?.();
    const from = { ...cam }, to = { cx: r.x + r.w / 2, cy: r.y + r.h / 2, z: fitZ(r) };
    if (reduced()) duration = 0.01;
    const o = { t: 0 };
    return new Promise((done) => { flight = gsap.to(o, {
      t: 1, duration, ease, overwrite: true,
      onUpdate() {
        const t = o.t;
        cam.z = from.z * Math.pow(to.z / from.z, t); // zoom in log space feels physical
        // keep the screen-space path straight: weight the pan by how far the zoom has progressed
        const k = Math.abs(Math.log(to.z / from.z)) < 1e-3 ? t : (1 / from.z - 1 / cam.z) / (1 / from.z - 1 / to.z);
        cam.cx = from.cx + (to.cx - from.cx) * k;
        cam.cy = from.cy + (to.cy - from.cy) * k;
      },
      onComplete: () => { flight = null; done(); },
    }); });
  }
  function jumpTo(r) { cam.cx = r.x + r.w / 2; cam.cy = r.y + r.h / 2; cam.z = fitZ(r); }
  function view() {
    const t = performance.now() / 1000;
    look.x += (look.tx - look.x) * 0.04; look.y += (look.ty - look.y) * 0.04;
    const z = cam.z * (reduced() ? 1 : 1 + 0.012 * Math.sin(t * 0.32)); // slow breathing
    const vw = VW() / z, vh = VH() / z;
    let cx = cam.cx + look.x * vw * 0.045, cy = cam.cy + look.y * vh * 0.035; // bounded free look
    cx = Math.min(Math.max(cx, vw / 2), geo.W - vw / 2);
    cy = Math.min(Math.max(cy, vh / 2), geo.H - vh / 2);
    return { cx, cy, z };
  }
  const toScreen = (v, x, y) => [VW() / 2 + (x - v.cx) * v.z, VH() / 2 + (y - v.cy) * v.z];
  function frame() {
    if (!alive) return;
    const v = view();
    for (const s of Object.values(stills)) {
      if (!s.on && !gsap.isTweening(s.el)) { s.el.style.visibility = 'hidden'; continue; }
      s.el.style.visibility = 'visible';
      const [x, y] = toScreen(v, s.rect.x, s.rect.y);
      s.el.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${(s.rect.w * v.z) / s.pw}, ${(s.rect.h * v.z) / s.ph})`;
    }
    const narrow = VW() < 720, W2 = VW();
    // reads first (no layout thrash): tag sizes (re-measured every 20 frames) and obstacle rects
    frameNo++;
    for (const t of tags.values()) if (!t.w || frameNo % 20 === 0) {
      const full = !t.el.classList.contains('compact');
      if (full) { t.w = t.el.offsetWidth; t.h = t.el.offsetHeight; t.hc = t.h - (t.el.querySelector('.meta')?.offsetHeight || 0); }
    }
    const obstacles = readObstacles();
    const placed = [];
    for (const t of tags.values()) {
      let [x, y] = toScreen(v, t.wx, t.wy); // re-anchored to its world position every frame
      const mx = narrow ? 90 : 120, top = narrow ? 120 : 96, bottom = VH() - (narrow ? 260 : 150);
      if (t.clickable) { // options stay reachable: pinned to the nearest edge when off screen
        const cx = Math.min(Math.max(x, mx), W2 - mx), cy = Math.min(Math.max(y, top), bottom);
        t.edge = cx !== x || cy !== y; x = cx; y = cy;
      } else { // greyed / pruned names stay at their real place; off screen = not shown
        t.off = x < -40 || x > W2 + 40 || y < 40 || y > VH() - 40;
      }
      placed.push({ t, x, y });
    }
    if (avoid.narration && obstacles.narration) chooseSide(placed, obstacles, narrow);
    // phones: when the options cannot all fit as full cards without covering each other, every option
    // becomes a name pill. Hysteresis: pills after ~0.3 s of overlap, full cards again after ~1.5 s clean.
    if (frameNo % 20 === 1 || !topLim) topLim = (parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--top-h')) || 76) + 10;
    // the dot marks the branch tip: a phone card starts just above it
    const fresh = () => placed.map((p) => ({ t: p.t, x: p.x, y: narrow ? p.y - p.t.h / 2 - 14 : p.y, ax: p.x, ay: p.y }));
    let laid;
    if (!narrow) { pillMode = false; pillRun = 0; laid = layoutWide(fresh(), obstacles.list); }
    else {
      laid = layoutLabels(fresh(), obstacles.list, false);
      pillRun = laid.childOverlap ? Math.max(1, pillRun + 1) : Math.min(-1, pillRun - 1);
      if (!pillMode && pillRun >= 18) pillMode = true;
      else if (pillMode && pillRun <= -90) pillMode = false;
      if (pillMode) laid = layoutLabels(fresh(), obstacles.list, true);
    }
    for (const p of laid) {
      const hidden = p.hidden || !!p.t.off;
      if (p.t.compactShown !== !!p.compact) { p.t.compactShown = !!p.compact; p.t.el.classList.toggle('compact', !!p.compact); }
      if (p.t.occluded !== hidden) { p.t.occluded = hidden; p.t.el.classList.toggle('occluded', hidden); }
      if (p.t.edgeShown !== !!p.t.edge) { p.t.edgeShown = !!p.t.edge; p.t.el.classList.toggle('edge', !!p.t.edge); }
      p.t.el.style.transform = `translate3d(${p.x}px, ${p.y}px, 0) translate(-50%, -50%)`;
      // the dot stays on the branch; a thin leader joins it to the card when the card had to move
      const dx = Math.round(p.ax - p.x), dy = Math.round(p.ay - (p.y + (p.compact ? p.t.hc : p.t.h) / 2));
      const key = `${dx},${dy}`;
      if (p.t.dotKey !== key) {
        p.t.dotKey = key;
        p.t.dot.style.transform = `translate(-50%, -50%) translate(${dx}px, ${dy}px)`;
        const h = p.compact ? p.t.hc : p.t.h, up = dy < -h / 2; // dot above the card: the leader leaves from its top edge
        const ly = up ? dy + h : dy, len = Math.hypot(dx, ly) - 8;
        p.t.lead.style.top = up ? '0' : '100%';
        p.t.lead.style.height = `${Math.max(0, len)}px`;
        p.t.lead.style.transform = `rotate(${Math.atan2(-dx, ly)}rad)`;
        p.t.lead.style.opacity = len > 10 ? 1 : 0;
      }
    }
    raf = requestAnimationFrame(frame);
  }
  // ---------- label layout: no card over another card, Lumi, the bubble or the dock ----------
  // Priority: options you can click > grey alternatives > pruned names. Each card tries its own place,
  // then vertical offsets (keeping last frame's choice first, so nothing flickers); a lower-priority
  // card that finds no free slot fades, an option stays visible at the least-overlapping slot.
  const PRIORITY = { child: 0, sibling: 1, pruned: 2 };
  const overlap = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  const rectAt = (x, y, t) => ({ left: x - t.w / 2 - 4, right: x + t.w / 2 + 4, top: y - t.h / 2 - 4, bottom: y + t.h / 2 + 4 });
  let pillMode = false, pillRun = 0, tagKey = '', topLim = 0;
  // Desktop: every option card sits at its own branch tip (card bottom just above the dot), siblings
  // share one top line when their branches are at similar heights, and cards that would touch are
  // spread sideways just enough (never relocated far from their branch). Deterministic: no flicker.
  function layoutWide(placed, fixed) {
    const W2 = VW(), gap = 14, live = placed.filter((p) => !p.t.off && p.t.w);
    for (const p of placed) { p.hidden = false; p.compact = false; }
    if (!live.length) return placed;
    const ys = live.map((p) => p.ay), spread = Math.max(...ys) - Math.min(...ys);
    // a card sits just above its dot; with no room above (a branch tip near the header) it hangs just
    // below it. Siblings whose tips are within ~90 px share one line.
    const fitsAbove = (y) => y - 16 - Math.max(...live.map((p) => p.t.h)) >= topLim;
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const above = live.every((p) => fitsAbove(p.ay));
    const line = spread <= 90 ? (above ? { bottom: minY - 16 } : fitsAbove(minY) ? { bottom: minY - 16 } : { top: maxY + 16 }) : null;
    for (const p of live) {
      const own = fitsAbove(p.ay) ? { bottom: p.ay - 16 } : { top: p.ay + 16 };
      const l = line || own;
      p.y = l.bottom != null ? l.bottom - p.t.h / 2 : l.top + p.t.h / 2;
      p.y = Math.min(Math.max(p.y, topLim + p.t.h / 2), VH() - 8 - p.t.h / 2);
      p.x = Math.min(Math.max(p.ax, p.t.w / 2 + 8), W2 - p.t.w / 2 - 8);
    }
    const box = (p) => ({ left: p.x - p.t.w / 2, right: p.x + p.t.w / 2, top: p.y - p.t.h / 2, bottom: p.y + p.t.h / 2 });
    // side panels (weather rail, Lumi's bubble/dock): a card slides sideways out of one, at most 200 px
    for (const p of live) for (const r of fixed) {
      const b = box(p);
      if (b.right <= r.left || b.left >= r.right || b.bottom <= r.top || b.top >= r.bottom) continue;
      const right = r.right + 8 - b.left, left = r.left - 8 - b.right;
      const d = Math.abs(left) < right ? left : right;
      if (Math.abs(d) <= 200) p.x += d;
    }
    // siblings never touch: push overlapping neighbours apart, half each, then keep them on screen
    const row = [...live].sort((a, b) => a.ax - b.ax);
    for (let pass = 0; pass < 8; pass++) {
      let moved = false;
      for (let i = 0; i < row.length - 1; i++) for (let j = i + 1; j < row.length; j++) {
        const a = row[i], b = row[j], A = box(a), B = box(b);
        if (A.bottom + gap <= B.top || B.bottom + gap <= A.top) continue;
        const need = (a.t.w + b.t.w) / 2 + gap - (b.x - a.x);
        if (need > 0.5) { a.x -= need / 2; b.x += need / 2; moved = true; }
      }
      for (const p of row) p.x = Math.min(Math.max(p.x, p.t.w / 2 + 8), W2 - p.t.w / 2 - 8);
      if (!moved) break;
    }
    return placed;
  }
  function layoutLabels(placed, fixed, pills = false) {
    const order = [...placed].sort((a, b) => (PRIORITY[a.t.status] ?? 3) - (PRIORITY[b.t.status] ?? 3) || a.y - b.y);
    const taken = [], minY = VW() < 720 ? 110 : 70, maxY = VH() - 40;
    for (const p of order) {
      p.hidden = false;
      if (p.t.off || !p.t.w) { continue; }
      const pill = pills && (p.t.status === 'child' || p.t.status === 'sibling') && p.t.hc ? { ...p.t, h: p.t.hc } : null;
      const tt = pill || p.t;
      const step = tt.h * 0.6 + 6, W2 = VW(), narrow = W2 < 720;
      const cands = [[0, 0]];
      for (let k = 1; k <= (narrow ? 7 : 4); k++) cands.push([0, -k * step], [0, k * step]);
      { // a card may also slide sideways (staying on screen)
        const sx = tt.w * 0.55 + 6;
        for (const dx of [-sx, sx]) for (let k = 0; k <= (narrow ? 5 : 3); k++) for (const dy of k ? [-k * step, k * step] : [0]) cands.push([dx, dy]);
      }
      if (p.t.slot) cands.unshift(p.t.slot);
      let best = null;
      const lo = p.t.w / 2 + 8, hi = W2 - p.t.w / 2 - 8; // a card is slid fully on screen, never dropped for touching an edge
      // the whole card stays between the header and the bottom edge (not just its centre)
      const yLo = minY + tt.h / 2, yHi = Math.max(yLo, VH() - 8 - tt.h / 2);
      for (let [dx, dy] of cands) {
        const x = narrow ? p.x + dx : Math.min(Math.max(p.x + dx, lo), Math.max(lo, hi)), y = Math.min(Math.max(p.y + dy, yLo), yHi);
        dx = x - p.x; dy = y - p.y;
        if (x < lo || x > hi) continue; // phones: sideways candidates cover the edges
        const r = rectAt(x, y, tt);
        const cost = taken.reduce((c, q) => c + overlap(r, q), 0) + fixed.reduce((c, q) => c + overlap(r, q), 0);
        if (cost === 0) { best = { dx, dy, r, cost }; break; }
        if (!best || cost < best.cost) best = { dx, dy, r, cost };
      }
      if (!best) { p.hidden = true; continue; }
      p.compact = !!pill;
      const pri = PRIORITY[p.t.status] ?? 3;
      if (best.cost > 0 && pill) { // already a pill: a grey alternative fades, an option takes the least-covered spot
        if (pri > 0) { p.hidden = true; p.t.slot = null; continue; }
        placed.childOverlap = true;
      } else if (best.cost > 0) {
        // no free slot: try the name only (a small pill) before fading a grey alternative, or before
        // letting an option overlap another card on a phone
        // (desktop options always stay full cards: there is room to move them instead)
        const small = (p.t.status === 'sibling' || (narrow && p.t.status === 'child')) && p.t.hc ? { ...p.t, h: p.t.hc } : null;
        const fit = small && cands.map(([dx, dy]) => [narrow ? dx : Math.min(Math.max(p.x + dx, lo), Math.max(lo, hi)) - p.x, dy])
          .map(([dx, dy]) => [dx, dy, rectAt(p.x + dx, p.y + dy, small)])
          .find(([dx, dy, r]) => r.top >= minY && r.bottom <= maxY + 40 && r.left >= 4 && r.right <= W2 - 4
            && !taken.some((q) => overlap(r, q)) && !fixed.some((q) => overlap(r, q)));
        if (fit) { p.compact = true; p.t.slot = null; p.x += fit[0]; p.y += fit[1]; taken.push(fit[2]); continue; }
        if (pri > 0) { p.hidden = true; p.t.slot = null; continue; }
        placed.childOverlap = true;
      }
      p.t.slot = [best.dx, best.dy]; p.x += best.dx; p.y += best.dy;
      taken.push(best.r);
    }
    return placed;
  }

  // ---------- collision avoidance: Lumi + bubble + dock vs branch cards (screen space) ----------
  const avoid = { narration: null, others: [] }; // refreshed every frame from the getters
  let getAvoid = () => ({ narration: null, others: [] });
  let frameNo = 0, side = 'left', sideSince = 0;
  const pad = 8;
  const hits = (x, y, t, o) => x + t.w / 2 + pad > o.left && x - t.w / 2 - pad < o.right && y + t.h / 2 + pad > o.top && y - t.h / 2 - pad < o.bottom;
  function readObstacles() {
    const g = getAvoid(); avoid.narration = g.narration || null; avoid.others = g.others || [];
    const list = [];
    let narration = null;
    if (avoid.narration?.isConnected) {
      const r = avoid.narration.getBoundingClientRect();
      if (r.width && r.height) { narration = r; list.push(r); }
    }
    for (const el of avoid.others) if (el?.isConnected) { const r = el.getBoundingClientRect(); if (r.width && r.height) list.push(r); }
    return { narration, list };
  }
  const overlapArea = (placed, r) => placed.reduce((sum, p) => {
    const w = Math.min(p.x + p.t.w / 2, r.right) - Math.max(p.x - p.t.w / 2, r.left);
    const h = Math.min(p.y + p.t.h / 2, r.bottom) - Math.max(p.y - p.t.h / 2, r.top);
    return sum + (w > 0 && h > 0 ? w * h * (p.t.clickable ? 2 : 1) : 0);
  }, 0);
  // put Lumi and the bubble on the freer side of the current view (opposite to where cards cluster)
  function chooseSide(placed, obstacles, narrow) {
    const n = obstacles.narration;
    if (narrow) { if (side !== 'left') setSide('left'); return; } // full-width on phones: nudge/fade only
    const dock = avoid.others[0]?.getBoundingClientRect?.();
    const w = n.width, h = n.height, gap = 28;
    const left = { left: gap, right: gap + w, top: VH() - gap - h, bottom: VH() - gap };
    const rb = dock && dock.height ? dock.top - 12 : VH() - gap;
    const right = { left: VW() - gap - w, right: VW() - gap, top: rb - h, bottom: rb };
    const cost = { left: overlapArea(placed, left), right: overlapArea(placed, right) };
    const other = side === 'left' ? 'right' : 'left';
    const now = performance.now();
    if (cost[other] * 1.3 + 400 < cost[side] && now - sideSince > 900) setSide(other); // hysteresis: no flicker
  }
  function setSide(s) {
    side = s; sideSince = performance.now();
    avoid.narration.classList.toggle('right', s === 'right');
    avoid.narration.closest?.('body')?.style.setProperty('--dock-h', `${(avoid.others[0]?.offsetHeight || 0) + 40}px`);
  }

  const onMove = (e) => {
    if (e.pointerType !== 'mouse') return;
    look.tx = (e.clientX / innerWidth - 0.5) * 2;
    look.ty = (e.clientY / innerHeight - 0.5) * 2;
  };
  addEventListener('pointermove', onMove);

  // ---------- labels ----------
  // items: [{id, status, name, meta (html), clickable}]
  function setTags(items) {
    const key = items.map((it) => it.id).join(',');
    if (key !== tagKey) { tagKey = key; pillMode = false; pillRun = 0; } // a new node: full cards first
    const keep = new Set();
    for (const it of items) {
      keep.add(it.id);
      let t = tags.get(it.id);
      if (!t) {
        const el = document.createElement('button');
        el.type = 'button';
        el.innerHTML = '<span class="card"><span class="name"></span><span class="meta"></span></span><span class="lead"></span><span class="dot"></span>';
        el.addEventListener('click', () => { if (t.clickable) onTagClick?.(it.id, t.status); });
        el.style.opacity = 0;
        labels.append(el);
        const [wx, wy] = geo.anchor(it.id);
        t = { el, wx, wy, dot: el.querySelector('.dot'), lead: el.querySelector('.lead') };
        tags.set(it.id, t);
        gsap.to(el, { opacity: 1, duration: 0.8, delay: 0.25, ease: 'power2.out' });
      }
      t.status = it.status; t.clickable = it.clickable;
      t.el.className = `tag ${it.status}${it.custom ? ' custom' : ''}${wx.breaking.has(it.id) ? ' breaking' : wx.holding.has(it.id) ? ' holding' : ''}`;
      t.compactShown = t.occluded = t.edgeShown = undefined; // className reset: layout classes come back next frame
      t.el.querySelector('.card').dataset.badge = it.custom || '';
      t.el.disabled = !it.clickable;
      t.el.tabIndex = it.clickable ? 0 : -1;
      t.el.setAttribute('aria-label', it.name);
      t.el.querySelector('.name').textContent = it.name;
      const m = t.el.querySelector('.meta');
      m.innerHTML = it.meta || '';
      m.hidden = !it.meta;
    }
    for (const [id, t] of tags) if (!keep.has(id)) {
      tags.delete(id);
      gsap.to(t.el, { opacity: 0, duration: 0.35, onComplete: () => t.el.remove() });
    }
  }

  // ---------- weather (#65): the sky the user does not choose ----------
  // 'weather:change' {weather, intensity, clear, pending, holding_node_ids, breaking_node_ids} from
  // web/src/weather. No new images: a tint over the sky, desaturated stills, canvas rain, a lightning
  // flash for a market crash, a cold cast for a job loss, and dimmed branches that stop holding.
  const stage = world.parentElement;
  const wxSky = document.createElement('div'); wxSky.className = 'wx-sky';
  const wxRain = document.createElement('canvas'); wxRain.className = 'wx-rain';
  const wxFlash = document.createElement('div'); wxFlash.className = 'wx-flash';
  for (const el of [wxSky, wxRain, wxFlash]) { el.setAttribute('aria-hidden', 'true'); stage?.insertBefore(el, labels); }
  const wx = { types: [], k: 0, holding: new Set(), breaking: new Set(), dimCodes: new Set(), drops: [], raf: 0, flashT: 0 };
  const RAINY = { recession: 1, market_crash: 1, job_loss: 0.6 };
  const rainLevel = () => Math.min(1, wx.types.reduce((a, t) => a + (RAINY[t] || 0), 0)) * (0.35 + 0.65 * wx.k);
  function rainFrame() {
    wx.raf = 0;
    const lvl = rainLevel();
    const c = wxRain.getContext('2d');
    if (!alive || !lvl || reduced() || document.hidden || !c) { c?.clearRect(0, 0, wxRain.width, wxRain.height); return; }
    const w = stage.clientWidth, h = stage.clientHeight;
    if (wxRain.width !== w || wxRain.height !== h) { wxRain.width = w; wxRain.height = h; }
    const want = Math.round(70 + 260 * lvl);
    while (wx.drops.length < want) wx.drops.push({ x: Math.random() * w, y: Math.random() * h, v: 9 + Math.random() * 9, l: 10 + Math.random() * 16 });
    wx.drops.length = want;
    c.clearRect(0, 0, w, h);
    c.strokeStyle = 'rgba(214, 226, 238, 0.42)'; c.lineWidth = 1; c.beginPath();
    for (const d of wx.drops) {
      c.moveTo(d.x, d.y); c.lineTo(d.x - d.l * 0.18, d.y + d.l);
      d.y += d.v; d.x -= d.v * 0.18;
      if (d.y > h) { d.y = -d.l; d.x = Math.random() * (w + 60); }
    }
    c.stroke();
    wx.raf = requestAnimationFrame(rainFrame);
  }
  function flash() {
    if (reduced() || document.hidden || !wx.types.includes('market_crash')) return;
    gsap.timeline().set(wxFlash, { opacity: 0 }).to(wxFlash, { opacity: 0.75, duration: 0.06 }).to(wxFlash, { opacity: 0.1, duration: 0.12 })
      .to(wxFlash, { opacity: 0.55, duration: 0.05 }).to(wxFlash, { opacity: 0, duration: 0.7, ease: 'power2.out' });
  }
  function setWeather(d = {}) {
    const types = (d.weather || []).map((w) => w.type);
    const crashNew = types.includes('market_crash') && !wx.types.includes('market_crash');
    wx.types = types; wx.k = d.clear || !types.length ? 0 : Math.max(0.15, Math.min(1, Number(d.intensity) || 0));
    if (stage) {
      stage.dataset.wx = types.join(' ');
      stage.style.setProperty('--wx-k', wx.k.toFixed(2));
      stage.classList.toggle('wx-on', wx.k > 0);
    }
    if (!d.pending) { // results arrived: which visible options still hold
      wx.holding = new Set(types.length ? d.holding_node_ids || [] : []);
      wx.breaking = new Set(types.length ? d.breaking_node_ids || [] : []);
      wx.dimCodes = new Set([...wx.breaking].flatMap(codesOf));
      for (const [id, t] of tags) { t.el.classList.toggle('breaking', wx.breaking.has(id)); t.el.classList.toggle('holding', !wx.breaking.has(id) && wx.holding.has(id)); }
      for (const s of Object.values(stills)) if (s.on) paintDim(s, wx.dimCodes);
    }
    if (crashNew) flash();
    clearInterval(wx.flashT); wx.flashT = types.includes('market_crash') ? setInterval(flash, 14000) : 0;
    if (!wx.raf && rainLevel()) wx.raf = requestAnimationFrame(rainFrame);
  }
  const onWeatherEvt = (e) => setWeather(e.detail || {});
  addEventListener('weather:change', onWeatherEvt);

  raf = requestAnimationFrame(frame);
  return {
    geo,
    /** Intro: close-up of the roots, over the master. */
    async intro() {
      showStill('master', true, { duration: 0.01 });
      const r = showStill('roots', true, { duration: 0.01 });
      jumpTo(geo.rectOf('roots'));
      prefetch(['c1', 'c2', 'c3']);
      await r.ready;
    },
    /** From the roots up to the whole tree. */
    async rise() {
      showStill('roots', false, { delay: 0.5, duration: 1.4 });
      await camTo(geo.viewRect('0'), { duration: 2.8, ease: 'power2.inOut' });
    },
    /** Show a node: the stills on its path, greyed branches, labels; fly the camera there. */
    /** Phase 1, before data: stills on the path and the camera flight start at once (optimistic). */
    go({ pathIds, current, deeper }) {
      currentId = current;
      setTags([]); // old labels leave; the new ones arrive with the data
      const want = new Set(['master']);
      for (const id of pathIds) want.add(geo.stillFor(id));
      const ready = [];
      for (const name of new Set([...want, ...Object.keys(stills)])) {
        if (want.has(name)) ready.push(showStill(name, true, { delay: deeper ? 0.7 : 0, duration: 1.1 }).ready);
        else if (stills[name]?.on) showStill(name, false, { duration: 0.8 });
      }
      const fly = camTo(geo.viewRect(current), { duration: deeper ? 2.0 : 1.6 });
      return Promise.all([fly, ...ready]);
    },
    /** Phase 2, with data: greyed branches, labels, next stills warmed in the HTTP cache. */
    async dress({ grey, tagItems, childIds = [] }) {
      await Promise.all(Object.values(stills).filter((s) => s.on).map((s) => s.ready));
      prefetch(childIds.map((id) => geo.ownStill(id)));
      for (const s of Object.values(stills)) if (s.on) { paintGrey(s, grey); paintDim(s, wx.dimCodes); }
      setTags(tagItems);
    },
    setTags, setWeather,
    /** Personal conditions changed: the camera breathes out and back while the branch's cards grow again. */
    async regrow() {
      if (reduced()) return;
      const stage = world.parentElement;
      stage?.classList.remove('regrowing'); void stage?.offsetWidth; stage?.classList.add('regrowing');
      setTimeout(() => stage?.classList.remove('regrowing'), 1800);
      const cards = [...tags.values()].map((t) => t.el.querySelector('.card')).filter(Boolean);
      gsap.fromTo(cards, { scale: 0.15, opacity: 0, y: 30, transition: 'none' },
        { scale: 1, opacity: 1, y: 0, duration: 0.9, stagger: 0.14, delay: 0.35, ease: 'back.out(1.5)', clearProps: 'transform,opacity,transition' });
      const r = geo.viewRect(currentId), k = 1.14;
      await camTo({ x: r.x - (r.w * (k - 1)) / 2, y: r.y - (r.h * (k - 1)) / 2, w: r.w * k, h: r.h * k }, { duration: 0.6, ease: 'power2.out' });
      await camTo(r, { duration: 1.1, ease: 'power3.inOut' });
    },
    /** Elements cards must not hide behind: the narration (Lumi + bubble, moved to the freer side) and others (the dock). */
    setAvoid(getter) { getAvoid = getter; },
    get side() { return side; },
    refit(current) { jumpTo(geo.viewRect(current)); },
    /** Chat panel open/closed: the scene keeps the remaining area and the camera re-frames the current node. */
    setInsets({ right = 0, bottom = 0 } = {}) {
      insetRight = Math.max(0, right); insetBottom = Math.max(0, bottom);
      const stage = world.parentElement;
      if (stage) { stage.style.right = `${insetRight}px`; stage.style.bottom = `${insetBottom}px`; }
      camTo(geo.viewRect(currentId), { duration: 0.6, ease: 'power2.out' });
    },
    destroy() {
      alive = false; cancelAnimationFrame(raf); removeEventListener('pointermove', onMove);
      removeEventListener('weather:change', onWeatherEvt); cancelAnimationFrame(wx.raf); clearInterval(wx.flashT);
      wxSky.remove(); wxRain.remove(); wxFlash.remove();
      for (const s of Object.values(stills)) release(s);
      for (const t of tags.values()) t.el.remove();
    },
  };
}
