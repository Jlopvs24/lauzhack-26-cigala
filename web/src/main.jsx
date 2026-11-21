import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import gsap from 'gsap';
import { createGuide } from '../assets/character/guide/guide.js';
import '../assets/character/guide/guide.css';
import { apiRequest } from './api.js';
import { pathToNode, validateTree } from './tree.js';
import Roots from './Roots.jsx';
import Dock from './Dock.jsx';
import { Assumptions } from './NodeDetail.jsx';
import { createScene } from './scene/scene.js';
import { visibleNodes, greyCodes } from './scene/geometry.js';
import { createVoice } from './scene/voice.js';
import { createNarrator, translateNode, t } from './scene/narration.js';
import { renderReport } from './scene/report.js';
import { UI, LANGS } from './scene/i18n.js';
import './app.css';

const CALL_URL = import.meta.env?.VITE_CALL_URL || 'http://127.0.0.1:8000/call';
const store = { get: (k, d) => { try { return localStorage.getItem(k) || d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } } };

function tagMeta(n, lang) {
  const m = n.result?.metrics, h = n.result?.health;
  if (!m || !(n.status === 'child' || n.status === 'sibling')) return '';
  const cash = m.first_negative_month != null ? `<span class="warn">${t(lang, 'tagShort')(m.first_negative_month + 1)}</span>` : t(lang, 'tagOk');
  return `${t(lang, 'tagHealth')} <b>${Math.round(h?.score ?? 0)}</b> · ${cash}`;
}

function App() {
  const [lang, setLang] = useState(() => (UI[store.get('cigala.lang', 'en')] ? store.get('cigala.lang', 'en') : 'en'));
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'light');
  const [started, setStarted] = useState(false);
  const [sheet, setSheet] = useState(null); // 'roots' | null
  const [panel, setPanel] = useState(null); // 'report' | 'chat' | null
  const [demoProfile, setDemoProfile] = useState(null);
  const [profile, setProfile] = useState(null); // null = the API's demo persona
  const [tree, setTree] = useState(null);
  const [overrides, setOverrides] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [bubble, setBubble] = useState('');
  const [muted, setMuted] = useState(false);
  const [lens, setLens] = useState(false);
  const [lensPending, setLensPending] = useState(false);
  const [messages, setMessages] = useState([]); // the session's conversation, never reset by navigation
  const [convOpen, setConvOpen] = useState(false);
  const [cost, setCost] = useState(0);

  const worldRef = useRef(null), labelsRef = useRef(null), lumiRef = useRef(null), introRef = useRef(null);
  const scene = useRef(null), lumi = useRef(null), voice = useRef(null);
  const narrator = useMemo(() => createNarrator(), []);
  const seen = useRef(new Map());
  const state = useRef({}); // latest values for imperative callbacks
  state.current = { tree, lang, profile, overrides, lens, busy };

  // dev-only hook for the browser check (visits every node directly); stripped from production builds
  if (import.meta.env?.DEV) window.__cigala = { go: (p) => go(p, { force: true }), begin: () => begin(null), get busy() { return state.current.busy; } };
  const addCost = (c) => { if (Number.isFinite(c) && c > 0) setCost((x) => x + c); };
  const path = tree ? pathToNode(tree.nodes, tree.current) : [];

  // ---------- scene, Lumi and voice: created once ----------
  useEffect(() => {
    let disposed = false;
    lumi.current = createGuide(lumiRef.current, { mood: 70 });
    voice.current = createVoice({
      onTalking: (on) => lumi.current?.setTalking(on),
      onNoVoice: (l) => setBubble((b) => (b.includes(t(l, 'noVoice')) ? b : `${b} ${t(l, 'noVoice')}`)),
    });
    createScene({ world: worldRef.current, labels: labelsRef.current, onTagClick: (id, status) => onTag(id, status) }).then(async (s) => {
      if (disposed) { s.destroy(); return; }
      scene.current = s;
      s.setAvoid(() => ({ narration: document.querySelector('.narration'), others: [document.querySelector('.dock'), document.querySelector('.nav-back')] }));
      await s.intro();
      if (introRef.current) gsap.from(introRef.current.children, { opacity: 0, y: 16, duration: 1, stagger: 0.12, ease: 'power3.out' });
    });
    apiRequest('/profiles/demo', { method: 'GET' }).then((d) => setDemoProfile(d?.profile || null)).catch(() => {});
    const onResize = () => { const s = state.current; if (s.tree) scene.current?.refit(s.tree.current); };
    addEventListener('resize', onResize);
    return () => { disposed = true; removeEventListener('resize', onResize); scene.current?.destroy(); voice.current?.stop(); lumi.current?.destroy?.(); };
  }, []);

  useEffect(() => { document.documentElement.lang = lang; store.set('cigala.lang', lang); }, [lang]);
  useEffect(() => { document.documentElement.dataset.theme = theme; store.set('cigala.theme', theme); }, [theme]);
  useEffect(() => { voice.current?.setMuted(muted); }, [muted]);

  // ---------- narration ----------
  function say(text, spoken = text) {
    setBubble(text);
    voice.current?.speak(spoken, state.current.lang);
  }
  function narrateNode(data, l = state.current.lang) {
    const p = state.current.profile;
    const n = narrator.next(data, l, p ? JSON.stringify(p).length : 'demo', p?.display_name || 'Alexia');
    setBubble(n.text);
    voice.current?.speak(n.speak, l);
    const cur = data.nodes.find((x) => x.node_id === data.current);
    if (cur?.result?.health?.score != null) lumi.current?.setMood(cur.result.health.score);
  }

  // ---------- data + camera ----------
  function tagItems(data, l) {
    return visibleNodes(data, seen.current)
      .filter((n) => n.node_id !== data.current && n.status !== 'chosen')
      .map((n) => ({ id: n.node_id, status: n.status, name: translateNode(n, l).label, meta: tagMeta(n, l), clickable: n.status === 'child' || n.status === 'sibling' }));
  }
  async function fetchTree(p, opts = {}) {
    const s = state.current;
    const body = { path: p, assumptions: opts.assumptions ?? s.overrides, uncertainty: opts.lens ?? s.lens };
    const prof = opts.profile !== undefined ? opts.profile : s.profile;
    if (prof) body.profile = prof;
    const data = validateTree(await apiRequest('/tree/expand', { body }));
    addCost(data.cost_usd);
    return data;
  }
  async function go(p, opts = {}) {
    if (state.current.busy && !opts.force) return;
    setBusy(true); setError('');
    voice.current?.unlock();
    voice.current?.stop();
    const deeper = p.length > (state.current.tree ? pathToNode(state.current.tree.nodes, state.current.tree.current).length : -1);
    try {
      const data = await fetchTree(p, opts);
      if (opts.assumptions) setOverrides(opts.assumptions);
      setTree(data);
      const vis = visibleNodes(data, seen.current);
      const l = state.current.lang;
      setTimeout(() => narrateNode(data, l), deeper ? 900 : 600);
      await scene.current?.show({
        pathIds: data.path, current: data.current, grey: greyCodes(vis), deeper,
        tagItems: tagItems(data, l), childIds: data.nodes.filter((n) => n.status === 'child').map((n) => n.node_id),
      });
    } catch (e) {
      setError(e instanceof TypeError ? t(state.current.lang, 'noEngine') : e.message);
    } finally { setBusy(false); }
  }
  function onTag(id, status) {
    const s = state.current;
    if (!s.tree || s.busy) return;
    const p = pathToNode(s.tree.nodes, s.tree.current);
    if (status === 'child') go([...p, id]);
    else if (status === 'sibling') go([...p.slice(0, -1), id]); // switch sideways, same level
  }
  function back() { const s = state.current; if (s.tree && !s.busy) { const p = pathToNode(s.tree.nodes, s.tree.current); if (p.length) go(p.slice(0, -1)); } }

  async function begin(prof) {
    if (started) return;
    voice.current?.unlock();
    setProfile(prof); setSheet(null); setStarted(true);
    narrator.reset(); seen.current.clear();
    await scene.current?.rise();
    go([], { profile: prof, force: true });
  }

  // relabel and re-narrate on language change (new language = new content)
  useEffect(() => {
    if (!tree) return;
    scene.current?.setTags(tagItems(tree, lang));
    narrateNode(tree, lang);
  }, [lang]); // eslint-disable-line react-hooks/exhaustive-deps

  // the uncertainty lens asks the engine for Monte Carlo only when switched on (#21)
  async function toggleLens(on) {
    setLens(on);
    const cur = tree?.nodes.find((n) => n.node_id === tree.current);
    if (!on || cur?.result?.metrics?.final_net_worth_p50 != null) return;
    setLensPending(true);
    try { setTree(await fetchTree(path, { lens: true })); } catch (e) { setError(e.message); } finally { setLensPending(false); }
  }

  // a lever's "try" button: recompute the whole visible tree with that one assumption overridden
  function applyLever(id, value) {
    if (!Number.isFinite(value)) return;
    const next = [...overrides.filter((o) => o.id !== id), { id, value }];
    go(path, { assumptions: next, force: true });
  }

  // keyboard + wheel: one level back, never further
  useEffect(() => {
    let acc = 0, last = 0;
    const onKey = (e) => { if (e.target.closest?.('input, textarea, select')) return; if (e.key === 'Escape') { if (panel) setPanel(null); else back(); } };
    const onWheel = (e) => {
      if (!started || e.target.closest?.('.drawer, .report')) return;
      const now = performance.now(); if (now - last > 400) acc = 0; last = now; acc += e.deltaY;
      if (acc < -160) { acc = 0; back(); }
    };
    addEventListener('keydown', onKey); addEventListener('wheel', onWheel, { passive: true });
    return () => { removeEventListener('keydown', onKey); removeEventListener('wheel', onWheel); };
  });


  const cur = tree?.nodes.find((n) => n.node_id === tree.current);
  const crumbs = tree ? tree.path.map((id) => tree.nodes.find((n) => n.node_id === id)).filter(Boolean) : [];
  const reportHTML = tree ? renderReport({ data: tree, lang, ui: UI[lang], tr: (n) => translateNode(n, lang), lens, lensPending, applied: overrides.length > 0 }) : '';

  return <>
    <main id="stage" aria-label="Financial tree">
      <div id="world" ref={worldRef} />
      <div className="grade" aria-hidden="true" /><div className="moon" aria-hidden="true" />
      <div className="mist mist-a" aria-hidden="true" /><div className="mist mist-b" aria-hidden="true" />
      <div className="vignette" aria-hidden="true" /><div className="grain" aria-hidden="true" />
      <div id="labels" ref={labelsRef} />
    </main>

    <header className="top">
      <div className="brand"><span className="mark" aria-hidden="true" />cigala</div>
      <nav id="crumbs" aria-label="Path">{crumbs.map((n) => <span key={n.node_id}>{translateNode(n, lang).label}</span>)}</nav>
      <div className="top-actions">
        <div className="seg" role="group" aria-label="Language">{Object.entries(LANGS).map(([k, v]) =>
          <button key={k} type="button" aria-pressed={k === lang} onClick={() => setLang(k)}>{v}</button>)}</div>
        <button className="ghost-btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? t(lang, 'light') : t(lang, 'dark')}</button>
        <button className="ghost-btn" aria-pressed={muted} onClick={() => { voice.current?.unlock(); setMuted(!muted); }}>{muted ? t(lang, 'soundOff') : t(lang, 'soundOn')}</button>
        {tree && <button className={`ghost-btn ${panel === 'report' ? 'on' : ''}`} onClick={() => setPanel(panel === 'report' ? null : 'report')}>{t(lang, 'report')}</button>}
      </div>
    </header>

    {started && path.length > 0 && <button className="nav-back" onClick={back} disabled={busy}>
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
      <span>{t(lang, 'back')}</span></button>}

    {!started && !sheet && <section className="intro" ref={introRef}>
      <p className="eyebrow">{t(lang, 'eyebrow')}</p>
      <h1>{t(lang, 'h1a')}<br /><em>{t(lang, 'h1b')}</em></h1>
      <p className="lede">{t(lang, 'lede')}</p>
      <div className="choices">
        <button className="primary" onClick={() => begin(null)}>{t(lang, 'demo')}</button>
        <button className="secondary" onClick={() => { voice.current?.unlock(); setSheet('roots'); }}>{t(lang, 'own')}</button>
      </div>
      <p className="demo-note">{t(lang, 'demoNote')}</p>
    </section>}

    {sheet === 'roots' && <section className="drawer sheet" aria-labelledby="roots-title">
      <button className="close" aria-label="Close" onClick={() => setSheet(null)}>×</button>
      <h2 className="sheet-title" id="roots-title">{t(lang, 'rootsTitle')}</h2>
      <p className="sheet-lede">{t(lang, 'rootsLede')}</p>
      {demoProfile ? <Roots open profile={demoProfile} busy={busy} onCost={addCost} onApply={(p) => begin(p)} />
        : <p>{t(lang, 'noEngine')}</p>}
    </section>}

    <aside className="narration" aria-live="polite">
      <div id="lumi" ref={lumiRef} />
      {bubble && !convOpen && <div className="say-card"><p>{bubble}</p></div>}
    </aside>

    {started && <Dock t={(k) => t(lang, k)} lang={lang} messages={messages} setMessages={setMessages} open={convOpen} setOpen={setConvOpen}
      disabled={!tree} context={{ profile, path, node_id: tree?.current, assumptions: overrides, weather: tree?.weather || [] }}
      onAnswer={(text) => say(text)} onCost={addCost} callUrl={CALL_URL} onUnlock={() => voice.current?.unlock()} />}

    {panel === 'report' && cur && <aside className="report drawer" aria-label="Report">
      <button className="close" aria-label="Close" onClick={() => setPanel(null)}>×</button>
      <div onClick={(e) => { // injected HTML: React's onChange does not see these inputs, clicks do
        if (e.target.id === 'lensToggle') { toggleLens(e.target.checked); return; }
        const b = e.target.closest?.('[data-lever]'); if (b && !busy) applyLever(b.dataset.lever, Number(b.dataset.value)); }}
        dangerouslySetInnerHTML={{ __html: reportHTML }} />
      <div className="drawer-inline"><Assumptions assumptions={tree.assumptions} busy={busy} onApply={(next) => go(path, { assumptions: next, force: true })} /></div>
      <p className="note">{t(lang, 'sessionCost')} USD {cost.toFixed(4)}</p>
    </aside>}

    {busy && started && <div className="loading" role="status">{t(lang, 'loading')}</div>}
    {error && <div className="error-toast" role="alert">{error}<button onClick={() => { setError(''); go(path, { force: true }); }}>{t(lang, 'retry')}</button></div>}
  </>;
}

createRoot(document.getElementById('root')).render(<App />);
