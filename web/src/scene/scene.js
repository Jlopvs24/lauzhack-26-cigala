// The photographic tree: matched 2K stills on one world plane, a camera that flies between their
// rectangles (zoom in log space), feathered greying of sibling/pruned branches from label maps,
// and HTML labels anchored to branch positions. Framework-free; main.jsx drives it.
import gsap from 'gsap';
import { createGeometry } from './geometry.js';

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
    const base = new Image(), grey = new Image();
    base.decoding = grey.decoding = 'async';
    base.alt = grey.alt = ''; base.draggable = grey.draggable = false;
    grey.className = 'grey';
    base.src = grey.src = BASE + st.src;
    el.append(base, grey);
    world.append(el);
    const s = { name, el, base, grey, pw, ph, rect: geo.rectOf(name), on: false, greyKey: '' };
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
  function release(s) {
    s.base.src = s.grey.src = '';
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
    for (const t of tags.values()) if (!t.w || frameNo % 20 === 0) { t.w = t.el.offsetWidth; t.h = t.el.offsetHeight; }
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
    for (const p of layoutLabels(placed, obstacles.list)) {
      const hidden = p.hidden || !!p.t.off;
      if (p.t.occluded !== hidden) { p.t.occluded = hidden; p.t.el.classList.toggle('occluded', hidden); }
      if (p.t.edgeShown !== !!p.t.edge) { p.t.edgeShown = !!p.t.edge; p.t.el.classList.toggle('edge', !!p.t.edge); }
      p.t.el.style.transform = `translate3d(${p.x}px, ${p.y}px, 0) translate(-50%, -50%)`;
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
  function layoutLabels(placed, fixed) {
    const order = [...placed].sort((a, b) => (PRIORITY[a.t.status] ?? 3) - (PRIORITY[b.t.status] ?? 3) || a.y - b.y);
    const taken = [], minY = VW() < 720 ? 110 : 70, maxY = VH() - 40;
    for (const p of order) {
      p.hidden = false;
      if (p.t.off || !p.t.w) { continue; }
      const step = p.t.h * 0.6 + 6, W2 = VW(), narrow = W2 < 720;
      const cands = [[0, 0]];
      for (let k = 1; k <= 4; k++) cands.push([0, -k * step], [0, k * step]);
      if (narrow) { // phones: a card may also slide sideways (staying on screen)
        const sx = p.t.w * 0.55 + 6;
        for (const dx of [-sx, sx]) for (let k = 0; k <= 3; k++) for (const dy of k ? [-k * step, k * step] : [0]) cands.push([dx, dy]);
      }
      if (p.t.slot) cands.unshift(p.t.slot);
      let best = null;
      for (const [dx, dy] of cands) {
        const x = p.x + dx, y = p.y + dy;
        if (y < minY || y > maxY || x - p.t.w / 2 < 4 || x + p.t.w / 2 > W2 - 4) continue;
        const r = rectAt(x, y, p.t);
        const cost = taken.reduce((c, q) => c + overlap(r, q), 0) + fixed.reduce((c, q) => c + overlap(r, q), 0);
        if (cost === 0) { best = { dx, dy, r, cost }; break; }
        if (!best || cost < best.cost) best = { dx, dy, r, cost };
      }
      if (!best) { p.hidden = true; continue; }
      if (best.cost > 0 && (PRIORITY[p.t.status] ?? 3) > 0) { p.hidden = true; p.t.slot = null; continue; }
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
    const keep = new Set();
    for (const it of items) {
      keep.add(it.id);
      let t = tags.get(it.id);
      if (!t) {
        const el = document.createElement('button');
        el.type = 'button';
        el.innerHTML = '<span class="card"><span class="name"></span><span class="meta"></span></span><span class="dot"></span>';
        el.addEventListener('click', () => { if (t.clickable) onTagClick?.(it.id, t.status); });
        el.style.opacity = 0;
        labels.append(el);
        const [wx, wy] = geo.anchor(it.id);
        t = { el, wx, wy };
        tags.set(it.id, t);
        gsap.to(el, { opacity: 1, duration: 0.8, delay: 0.25, ease: 'power2.out' });
      }
      t.status = it.status; t.clickable = it.clickable;
      t.el.className = `tag ${it.status}`;
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
      for (const s of Object.values(stills)) if (s.on) paintGrey(s, grey);
      setTags(tagItems);
    },
    setTags,
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
      for (const s of Object.values(stills)) release(s);
      for (const t of tags.values()) t.el.remove();
    },
  };
}
