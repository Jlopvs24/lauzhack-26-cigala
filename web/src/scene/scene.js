// The photographic tree: matched 2K stills on one world plane, a camera that flies between their
// rectangles (zoom in log space), feathered greying of sibling/pruned branches from label maps,
// and HTML labels anchored to branch positions. Framework-free; main.jsx drives it.
import gsap from 'gsap';
import { createGeometry } from './geometry.js';

const BASE = `${import.meta.env?.BASE_URL || '/'}tree/`;
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const loadImg = (src) => new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = src; });

export async function createScene({ world, labels, onTagClick }) {
  const meta = await (await fetch(`${BASE}stills.json`)).json();
  const geo = createGeometry(meta);
  const stills = {};
  const tags = new Map();
  const cam = { cx: geo.W / 2, cy: geo.H / 2, z: 1 };
  const look = { x: 0, y: 0, tx: 0, ty: 0 };
  let raf = 0, alive = true;

  function getStill(name) {
    if (stills[name]) return stills[name];
    const el = document.createElement('div');
    el.className = name === 'master' ? 'still master' : 'still';
    el.style.zIndex = name === 'master' ? 0 : name.split('_').length + (name === 'roots' ? 0 : 0);
    const base = document.createElement('canvas'), grey = document.createElement('canvas');
    grey.className = 'grey';
    el.append(base, grey);
    world.append(el);
    const s = { name, el, base, grey, rect: geo.rectOf(name), on: false, greyKey: '' };
    s.ready = Promise.all([loadImg(BASE + meta.stills[name].src), loadImg(BASE + meta.stills[name].lab)]).then(([img, lab]) => {
      for (const c of [base, grey]) { c.width = img.naturalWidth; c.height = img.naturalHeight; }
      base.getContext('2d').drawImage(img, 0, 0);
      s.rgb = base.getContext('2d').getImageData(0, 0, base.width, base.height);
      const t = document.createElement('canvas'); t.width = base.width; t.height = base.height;
      const tc = t.getContext('2d'); tc.drawImage(lab, 0, 0, t.width, t.height);
      s.lab = tc.getImageData(0, 0, t.width, t.height).data;
    });
    stills[name] = s;
    return s;
  }
  function paintGrey(s, set) {
    const key = [...set].sort().join(',');
    if (!s.rgb || s.greyKey === key) return;
    s.greyKey = key;
    const w = s.grey.width, h = s.grey.height;
    if (!s.desat) { // whole frame desaturated and lifted toward the mist (the sky barely changes)
      s.desat = document.createElement('canvas'); s.desat.width = w; s.desat.height = h;
      const o = new ImageData(w, h), src = s.rgb.data, d = o.data;
      for (let i = 0; i < d.length; i += 4) {
        const v = (0.3 * src[i] + 0.59 * src[i + 1] + 0.11 * src[i + 2]) * 0.64 + 212 * 0.36;
        d[i] = v + 2; d[i + 1] = v + 3; d[i + 2] = v + 6; d[i + 3] = 255;
      }
      s.desat.getContext('2d').putImageData(o, 0, 0);
    }
    // region mask at 1/4 resolution, feathered with a blur so limb boundaries melt instead of cutting
    const q = 4, mw = Math.ceil(w / q), mh = Math.ceil(h / q);
    const m = document.createElement('canvas'); m.width = mw; m.height = mh;
    const md = new ImageData(mw, mh), lab = s.lab;
    for (let y = 0; y < mh; y++) for (let x = 0; x < mw; x++) {
      if (set.has(lab[((y * q) * w + x * q) * 4])) md.data[(y * mw + x) * 4 + 3] = 255;
    }
    m.getContext('2d').putImageData(md, 0, 0);
    const ctx = s.grey.getContext('2d');
    ctx.save();
    ctx.clearRect(0, 0, w, h);
    ctx.drawImage(s.desat, 0, 0);
    ctx.globalCompositeOperation = 'destination-in';
    ctx.filter = `blur(${Math.round(w / 60)}px)`;
    ctx.drawImage(m, 0, 0, w, h);
    ctx.restore();
    if (!reduced()) gsap.fromTo(s.grey, { opacity: 0 }, { opacity: 1, duration: 1.1, ease: 'power2.out' });
    else s.grey.style.opacity = 1;
  }
  function release(s) {
    for (const c of [s.base, s.grey, s.desat]) if (c) { c.width = 0; c.height = 0; }
    s.el.remove();
    delete stills[s.name];
  }
  function showStill(name, on, { delay = 0, duration = 1.0 } = {}) {
    const s = getStill(name);
    if (s.on === on) return s;
    s.on = on;
    s.ready.then(() => gsap.to(s.el, {
      opacity: on ? 1 : 0, duration: reduced() ? 0.01 : duration, delay, ease: 'power1.inOut', overwrite: true,
      onComplete: () => { if (!s.on && name !== 'master' && stills[name] === s) release(s); }, // 2K canvases are heavy
    }));
    return s;
  }
  const fetched = new Set();
  function prefetch(names) { // warm the HTTP cache only; decoding happens when the still is shown
    for (const n of names) if (n && meta.stills[n] && !fetched.has(n)) { fetched.add(n); new Image().src = BASE + meta.stills[n].src; }
  }

  // ---------- camera ----------
  const fitZ = (r) => Math.max(innerWidth / r.w, innerHeight / r.h);
  function camTo(r, { duration = 1.8, ease = 'power3.inOut' } = {}) {
    const from = { ...cam }, to = { cx: r.x + r.w / 2, cy: r.y + r.h / 2, z: fitZ(r) };
    if (reduced()) duration = 0.01;
    const o = { t: 0 };
    return new Promise((done) => gsap.to(o, {
      t: 1, duration, ease, overwrite: true,
      onUpdate() {
        const t = o.t;
        cam.z = from.z * Math.pow(to.z / from.z, t); // zoom in log space feels physical
        // keep the screen-space path straight: weight the pan by how far the zoom has progressed
        const k = Math.abs(Math.log(to.z / from.z)) < 1e-3 ? t : (1 / from.z - 1 / cam.z) / (1 / from.z - 1 / to.z);
        cam.cx = from.cx + (to.cx - from.cx) * k;
        cam.cy = from.cy + (to.cy - from.cy) * k;
      },
      onComplete: done,
    }));
  }
  function jumpTo(r) { cam.cx = r.x + r.w / 2; cam.cy = r.y + r.h / 2; cam.z = fitZ(r); }
  function view() {
    const t = performance.now() / 1000;
    look.x += (look.tx - look.x) * 0.04; look.y += (look.ty - look.y) * 0.04;
    const z = cam.z * (reduced() ? 1 : 1 + 0.012 * Math.sin(t * 0.32)); // slow breathing
    const vw = innerWidth / z, vh = innerHeight / z;
    let cx = cam.cx + look.x * vw * 0.045, cy = cam.cy + look.y * vh * 0.035; // bounded free look
    cx = Math.min(Math.max(cx, vw / 2), geo.W - vw / 2);
    cy = Math.min(Math.max(cy, vh / 2), geo.H - vh / 2);
    return { cx, cy, z };
  }
  const toScreen = (v, x, y) => [innerWidth / 2 + (x - v.cx) * v.z, innerHeight / 2 + (y - v.cy) * v.z];
  function frame() {
    if (!alive) return;
    const v = view();
    for (const s of Object.values(stills)) {
      if (!s.on && !gsap.isTweening(s.el)) { s.el.style.visibility = 'hidden'; continue; }
      s.el.style.visibility = 'visible';
      const [x, y] = toScreen(v, s.rect.x, s.rect.y);
      s.el.style.width = s.base.width + 'px'; s.el.style.height = s.base.height + 'px';
      s.el.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${(s.rect.w * v.z) / (s.base.width || 1)}, ${(s.rect.h * v.z) / (s.base.height || 1)})`;
    }
    const narrow = innerWidth < 720;
    for (const t of tags.values()) {
      let [x, y] = toScreen(v, t.wx, t.wy);
      const mx = narrow ? 90 : 120;
      x = Math.min(Math.max(x, mx), innerWidth - mx); y = Math.min(Math.max(y, narrow ? 120 : 96), innerHeight - (narrow ? 260 : 150)); // keep off-screen branches reachable
      t.el.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, -50%)`;
    }
    raf = requestAnimationFrame(frame);
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
    async show({ pathIds, current, grey, tagItems, childIds = [], deeper }) {
      const want = new Set(['master']);
      for (const id of pathIds) want.add(geo.stillFor(id));
      for (const name of new Set([...want, ...Object.keys(stills)])) {
        if (want.has(name)) { const s = showStill(name, true, { delay: deeper ? 0.7 : 0, duration: 1.1 }); await s.ready; }
        else if (stills[name]?.on) showStill(name, false, { duration: 0.8 });
      }
      prefetch(childIds.map((id) => geo.ownStill(id)));
      for (const s of Object.values(stills)) if (s.on) paintGrey(s, grey);
      setTags(tagItems);
      await camTo(geo.viewRect(current), { duration: deeper ? 2.0 : 1.6 });
    },
    setTags,
    refit(current) { jumpTo(geo.viewRect(current)); },
    destroy() {
      alive = false; cancelAnimationFrame(raf); removeEventListener('pointermove', onMove);
      for (const s of Object.values(stills)) release(s);
      for (const t of tags.values()) t.el.remove();
    },
  };
}
