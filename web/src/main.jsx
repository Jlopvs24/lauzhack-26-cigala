import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import gsap from 'gsap';
import { createGuide } from '../assets/character/guide/guide.js';
import '../assets/character/guide/guide.css';
import { apiRequest } from './api.js';
import { pathToNode, validateTree } from './tree.js';
import Roots from './Roots.jsx';
import ChatPanel from './ChatPanel.jsx';
import { Assumptions } from './NodeDetail.jsx';
import { createScene } from './scene/scene.js';
import { visibleNodes, greyCodes } from './scene/geometry.js';
import { createVoice } from './scene/voice.js';
import { createNarrator, translateNode, openingFor, t } from './scene/narration.js';
import { splitSentences } from './scene/voice.js';
import { renderReport } from './scene/report.js';
import { cardBullets } from './scene/headline.js';
import PathReport from './report/PathReport.jsx';
import Verified from './Verified.jsx';
import { MakeItMine, YourConditions, personalFields, personalStore, PROPOSAL_EVENT, CHANGE_EVENT } from './personalize/index.js';
import WeatherControl from './weather/WeatherControl.jsx';
import { CompareRoot, CompareOptionsButton, cardCompareHTML, cardStripEnabled, compareSiblings, compareStore, pinHTML } from './compare/index.js';
import { eventDetail, stormLine, stormSummary } from './weather/weatherModel.js';
import { UI, LANGS } from './scene/i18n.js';
import './app.css';

const CALL_URL = import.meta.env?.VITE_CALL_URL || 'http://127.0.0.1:8000/call';
const store = { get: (k, d) => { try { return localStorage.getItem(k) || d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } } };

// Two slots per card (docs/report-spec.md §1): A "does it hold?", B "what it trades" + vs before this choice.
const escHTML = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
// The session's personal conditions in the engine's shape (docs/contracts.md: node_patches is
// {node_id: [interventions]}); accepts the store's list form too.
function engineFields() {
  const f = { ...personalFields() };
  if (Array.isArray(f.node_patches)) {
    f.node_patches = f.node_patches.reduce((o, p) => { (o[p.node_id] ||= []).push(...(p.interventions || [])); return o; }, {});
    if (!Object.keys(f.node_patches).length) delete f.node_patches;
  }
  return f;
}

// + the compare strip (where this option sits among its siblings) and a "+" pin (web/src/compare)
function tagMeta(n, lang, cmp = {}) {
  if (!n.result || !(n.status === 'child' || n.status === 'sibling')) return '';
  const c = cardBullets(n.result, lang);
  if (!c) return '';
  // a title + two plain bullets; the plan check is only a small coloured dot; compare is the corner "+"
  const dot = `<i class="pc-dot ${c.level}" aria-hidden="true"></i>`;
  const list = `<ul class="plain">${c.bullets.map((b) => `<li>${escHTML(b)}</li>`).join('')}</ul>`;
  const pin = cmp.path ? pinHTML(n.status === 'child' ? [...cmp.path, n.node_id] : [...cmp.path.slice(0, -1), n.node_id], translateNode(n, lang).label, lang) : '';
  // the position strip is opt-in (?strip=1); by default the comparison view carries position and deltas
  const strip = cmp.sib && cardStripEnabled() ? cardCompareHTML(n, cmp.nodes, { lang, label: (id, l) => translateNode({ node_id: id, label: l }, lang).label, cmp: cmp.sib }) : '';
  return dot + list + strip + pin;
}

function BackButton({ className, onClick, label }) {
  return <button className={className} onClick={onClick}>
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
    <span>{label}</span></button>;
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
  const [convOpen, setConvOpen] = useState(false);
  const [docked, setDocked] = useState(false); // a docked Lumi (bottom-right, thread 10) shows the narration instead
  const sayOut = useRef({ text: '', lang: 'en', speaking: false });
  const emitSay = () => dispatchEvent(new CustomEvent('lumi:say', { detail: { ...sayOut.current } }));
  const [pathReport, setPathReport] = useState(false);
  const [cost, setCost] = useState(0);
  const [noVoice, setNoVoice] = useState(''); // language with no voice at all on this device
  const [weather, setWeather] = useState([]); // #65: things the user does not choose, on every visible node

  const worldRef = useRef(null), labelsRef = useRef(null), lumiRef = useRef(null), introRef = useRef(null);
  const scene = useRef(null), lumi = useRef(null), voice = useRef(null);
  const narrator = useMemo(() => createNarrator(), []);
  const seen = useRef(new Map());
  const state = useRef({}); // latest values for imperative callbacks
  state.current = { tree, lang, profile, overrides, lens, busy, panel, pathReport, weather };

  // dev-only hook for the browser check (visits every node directly); stripped from production builds
  if (import.meta.env?.DEV) window.__cigala = { go: (p) => go(p, { force: true }), begin: () => begin(null), get busy() { return state.current.busy; } };
  const addCost = (c) => { if (Number.isFinite(c) && c > 0) setCost((x) => x + c); };
  const path = tree ? pathToNode(tree.nodes, tree.current) : [];

  // ---------- scene, Lumi and voice: created once ----------
  useEffect(() => {
    let disposed = false;
    lumi.current = createGuide(lumiRef.current, { mood: 70 });
    voice.current = createVoice({
      // Lumi's voice -> the character and the docked Lumi (thread 10): 'lumi:say' {text, lang, speaking},
      // 'lumi:level' {level 0..1, ~30 fps}. A dock announces itself with 'lumi:dock' {mounted}.
      onTalking: (on) => { lumi.current?.setTalking(on); sayOut.current.speaking = on; emitSay(); },
      onLevel: (level) => { lumi.current?.setMouthLevel?.(level); dispatchEvent(new CustomEvent('lumi:level', { detail: { level } })); },
      onNoVoice: (l) => setNoVoice(l), // a discreet "DE: text only" note, not a sentence in the bubble
    });
    createScene({ world: worldRef.current, labels: labelsRef.current, onTagClick: (id, status) => onTag(id, status) }).then(async (s) => {
      if (disposed) { s.destroy(); return; }
      scene.current = s;
      s.setAvoid(() => ({ narration: document.querySelector('.narration'), others: [document.querySelector('.chatp-dock-wrap'), ...document.querySelectorAll('.nav-back'), 
        document.querySelector('.top .brand'), ...document.querySelectorAll('#crumbs > span'), document.querySelector('.top-actions'), document.querySelector('.wx'), document.querySelector('.leaf-cta'),
        ...document.querySelectorAll('[data-layout-obstacle]')].filter(Boolean) })); // any panel can opt in (weather rail, Lumi dock)
      await s.intro();
      if (introRef.current) gsap.from(introRef.current.children, { opacity: 0, y: 16, duration: 1, stagger: 0.12, ease: 'power3.out' });
    });
    apiRequest('/profiles/demo', { method: 'GET' }).then((d) => setDemoProfile(d?.profile || null)).catch(() => {});
    const onResize = () => { const s = state.current; if (s.tree) scene.current?.refit(s.tree.current); };
    addEventListener('resize', onResize);
    // the header's real height (it wraps on phones): what sits under it is placed from --top-h
    const top = document.querySelector('header.top');
    const ro = top && new ResizeObserver(() => document.documentElement.style.setProperty('--top-h', `${Math.round(top.getBoundingClientRect().bottom)}px`));
    if (top) ro.observe(top);
    // Lluc's chat panel (#34): 'panel:open' {side: 'right'|'bottom', width, height} on open/resize, 'panel:close'
    const onPanel = (e) => { const d = e.detail || {}; scene.current?.setInsets(d.side === 'bottom' ? { bottom: d.height || 0 } : { right: d.width || 0 }); };
    const onPanelClose = () => scene.current?.setInsets({});
    addEventListener('panel:open', onPanel); addEventListener('panel:close', onPanelClose);
    return () => { disposed = true; ro?.disconnect(); removeEventListener('resize', onResize); removeEventListener('panel:open', onPanel); removeEventListener('panel:close', onPanelClose); scene.current?.destroy(); voice.current?.dispose(); lumi.current?.destroy?.(); };
  }, []);

  useEffect(() => { sayOut.current.text = bubble; sayOut.current.lang = lang; emitSay(); }, [bubble, lang]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const on = (e) => { setDocked(!!e.detail?.mounted); if (e.detail?.mounted) emitSay(); };
    addEventListener('lumi:dock', on);
    return () => removeEventListener('lumi:dock', on);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { document.documentElement.lang = lang; store.set('cigala.lang', lang); }, [lang]);
  useEffect(() => { document.documentElement.dataset.theme = theme; store.set('cigala.theme', theme); }, [theme]);
  useEffect(() => { voice.current?.setMuted(muted); }, [muted]);

  // ---------- narration ----------
  const reportOpen = () => state.current.panel === 'report' || state.current.pathReport;
  function say(text, spoken = text) {
    setBubble(text);
    if (!reportOpen()) voice.current?.speak(spoken, state.current.lang);
  }
  function narrateNode(data, l = state.current.lang) {
    const p = state.current.profile;
    const n = narrator.next(data, l, p ? JSON.stringify(p).length : 'demo', p?.display_name || 'Alexia');
    setBubble(n.text);
    if (!reportOpen()) voice.current?.speak(n.speak, l); // marked as narrated either way: no re-read later
    // while the user reads, warm the voice with each child's opening (name + first sentence)
    voice.current?.prefetch(data.nodes.filter((x) => x.status === 'child').map((x) => splitSentences(openingFor(x, l)).slice(0, 2).join(' ')).filter(Boolean), l);
    const cur = data.nodes.find((x) => x.node_id === data.current);
    if (cur?.result?.health?.score != null) lumi.current?.setMood(cur.result.health.score);
  }

  // ---------- data + camera ----------
  function tagItems(data, l) {
    const cmp = { nodes: data.nodes, sib: compareSiblings(data.nodes), path: (data.path || []).filter((id) => id !== '0') };
    return visibleNodes(data, seen.current)
      .filter((n) => n.node_id !== data.current && n.status === 'child') // only the options: Back changes the earlier choice
      .map((n) => ({ id: n.node_id, status: n.status, name: translateNode(n, l).label, meta: tagMeta(n, l, cmp), clickable: n.status === 'child' || n.status === 'sibling',
        custom: (n.custom || n.origin === 'user' || personalStore.isCustom(n.node_id)) ? t(l, 'yours')
          : (n.patched || n.inherits_patch || personalStore.forNode(n.node_id)?.length) ? t(l, 'yoursPatched') : '' }));
  }
  // One expand in flight: a new navigation aborts the stale one. Tree growth asks for no exploration
  // (fast path, #33); the report loads it lazily for the current node only.
  const inflight = useRef(null);
  const target = useRef([]); // the path being navigated to (Back and clicks act on it, not on stale data)
  async function fetchTree(p, opts = {}, signal) {
    const s = state.current;
    const body = { path: p, assumptions: opts.assumptions ?? s.overrides, uncertainty: opts.lens ?? s.lens, exploration: !!opts.exploration, ...engineFields(),
      weather: opts.weather ?? s.weather };
    const prof = opts.profile !== undefined ? opts.profile : s.profile;
    if (prof) body.profile = prof;
    const data = validateTree(await apiRequest('/tree/expand', { body, signal }));
    addCost(data.cost_usd);
    return data;
  }
  async function go(p, opts = {}) {
    inflight.current?.abort();
    const ctl = new AbortController(); inflight.current = ctl;
    target.current = p;
    setBusy(true); setError('');
    voice.current?.unlock();
    voice.current?.stop();
    const prev = state.current.tree ? pathToNode(state.current.tree.nodes, state.current.tree.current).length : -1;
    const deeper = p.length > prev;
    scene.current?.go({ pathIds: ['0', ...p], current: p.at(-1) || '0', deeper }); // camera moves now
    try {
      const data = await fetchTree(p, opts, ctl.signal);
      if (ctl.signal.aborted) return;
      if (opts.assumptions) setOverrides(opts.assumptions);
      setTree(data);
      const vis = visibleNodes(data, seen.current);
      const l = state.current.lang;
      const w = opts.weather ?? state.current.weather;
      // weather:change (#65) for the visual layer: which visible options hold under this weather
      if (opts.weatherChanged || w.length) dispatchEvent(new CustomEvent('weather:change', { detail: eventDetail(w, data, false) }));
      if (opts.weatherChanged && w.length) say(stormLine(l, w, stormSummary(data)));
      else narrateNode(data, l); // labels and narration arrive with the data; the flight continues underneath
      await scene.current?.dress({ grey: greyCodes(vis), tagItems: tagItems(data, l), childIds: data.nodes.filter((n) => n.status === 'child').map((n) => n.node_id) });
      if (opts.regrow && !ctl.signal.aborted) scene.current?.regrow();
    } catch (e) {
      if (ctl.signal.aborted || e.name === 'AbortError') return;
      setError(e instanceof TypeError ? t(state.current.lang, 'noEngine') : /timed? ?out|TimeoutError/i.test(`${e.name} ${e.message}`) ? t(state.current.lang, 'slow') : e.message);
    } finally { if (inflight.current === ctl) setBusy(false); } // busy = data only: clicks and Back can interrupt a flight
  }
  function onTag(id, status) {
    const p = target.current;
    if (status === 'child') go([...p, id]);
    else if (status === 'sibling') go([...p.slice(0, -1), id]); // switch sideways, same level
  }
  function onWeather(w) {
    setWeather(w);
    dispatchEvent(new CustomEvent('weather:change', { detail: eventDetail(w, null, true) }));
    go(target.current, { weather: w, weatherChanged: true, force: true });
  }
  function back() { const p = target.current; if (state.current.tree && p.length) go(p.slice(0, -1)); }

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
    try { setTree(await fetchTree(path, { lens: true, exploration: true })); } catch (e) { setError(e.message); } finally { setLensPending(false); }
  }

  // the comparison selection changed: redraw the cards' "+" pins (full / added states)
  useEffect(() => compareStore.subscribe(() => { const s = state.current; if (s.tree) scene.current?.setTags(tagItems(s.tree, s.lang)); }), []); // eslint-disable-line react-hooks/exhaustive-deps

  // personal conditions changed (confirmed, removed, cleared): re-expand with them, and the branch re-grows
  useEffect(() => {
    const on = () => { if (state.current.tree) go(target.current, { force: true, regrow: true }); };
    addEventListener(CHANGE_EVENT, on);
    return () => removeEventListener(CHANGE_EVENT, on);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // a report opening stops Lumi at once (speech and any TTS in flight)
  useEffect(() => { if (panel === 'report' || pathReport) voice.current?.stop(); }, [panel, pathReport]);

  // exploration only when the report is open, for the current node, cancelled when it changes
  const [explored, setExplored] = useState(null);
  useEffect(() => {
    if (panel !== 'report' || !tree || busy) return;
    const cur = tree.nodes.find((n) => n.node_id === tree.current);
    if (cur?.result?.exploration) return; // already there (API without the fast path)
    const key = JSON.stringify([path, overrides, lens, engineFields(), weather]);
    if (explored?.key === key) return;
    const ctl = new AbortController();
    const body = { path, assumptions: overrides, weather, ...(profile ? { profile } : {}), ...engineFields() };
    apiRequest('/tree/explore', { body, signal: ctl.signal })
      .then((x) => setExplored({ key, data: { ...tree, nodes: tree.nodes.map((n) => (n.node_id === tree.current
        ? { ...n, result: { ...n.result, exploration: x.exploration, sensitivity: x.sensitivity ?? n.result?.sensitivity } } : n)) } }))
      .catch((e) => { // API without /tree/explore: one expand with exploration
        if (ctl.signal.aborted || !/40[45]/.test(e.message)) return;
        fetchTree(path, { exploration: true }, ctl.signal).then((d) => setExplored({ key, data: d })).catch(() => {});
      });
    return () => ctl.abort();
  }, [panel, tree, busy]); // eslint-disable-line react-hooks/exhaustive-deps
  const exploredKey = JSON.stringify([path, overrides, lens, engineFields(), weather]);
  const reportTree = explored?.key === exploredKey ? explored.data : tree;

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
  const reportHTML = reportTree ? renderReport({ data: reportTree, lang, ui: UI[lang], tr: (n) => translateNode(n, lang), lens, lensPending, applied: overrides.length > 0 }) : '';

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
        <Verified lang={lang} />
        {started && tree && !busy && !pathReport && <CompareOptionsButton tree={tree} lang={lang} className="ghost-btn cmp-options-head" />}
        {tree && <button className={`ghost-btn ${panel === 'report' ? 'on' : ''}`} onClick={() => setPanel(panel === 'report' ? null : 'report')}>{t(lang, 'report')}</button>}
      </div>
    </header>

    {started && path.length > 0 && <BackButton className="nav-back nav-back-wide" onClick={back} label={t(lang, 'back')} />}
    {started && tree && !busy && !pathReport && <div className="cmp-options-mount"><CompareOptionsButton tree={tree} lang={lang} /></div>}
    {started && <CompareRoot lang={lang} tr={(n) => translateNode(n, lang)} profile={profile} assumptions={overrides} weather={tree?.weather} />}

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

    <aside className={`narration${docked ? ' docked' : ''}`}>
      <div id="lumi" ref={lumiRef} />
      <div className="say-col">
        {/* phones: Back rides above the bubble, so the bubble can never cover it */}
        {started && path.length > 0 && <BackButton className="nav-back nav-back-phone" onClick={back} label={t(lang, 'back')} />}
        {bubble && !convOpen && <div className="say-card" aria-live="polite"><p>{bubble}</p>
          {noVoice === lang && !muted && <span className="voice-note" title={t(lang, 'noVoice')}>{lang.toUpperCase()}: {t(lang, 'textOnly')}</span>}</div>}
      {started && cur && cur.node_id !== '0' && !pathReport && <div className="pz-mount">
        <MakeItMine key={cur.node_id} lang={lang} node={cur} path={path} profile={profile} assumptions={overrides}
          tr={(n) => translateNode(n, lang)} labelOf={(id) => tree.assumptions?.find((a) => a.id === id)?.label || id}
          onOpenChange={(open) => { if (open) voice.current?.stop(); }} compact /></div>}
      </div>
    </aside>

    {started && tree && <WeatherControl lang={lang} tree={tree} busy={busy} onChange={onWeather} />}
    {/* the chat stays mounted (its history survives) but never floats over a report */}
    {started && <div className="chat-host" hidden={pathReport || panel === 'report'}><ChatPanel lumi lang={lang} disabled={!tree} callUrl={CALL_URL} onOpenChange={setConvOpen}
      context={{ profile, path, node_id: tree?.current, assumptions: overrides, weather: tree?.weather || [], ...engineFields() }}
      onAnswer={(text, d) => { say(text); if (d?.personalize) dispatchEvent(new CustomEvent(PROPOSAL_EVENT, { detail: { node_id: tree?.current, ...d.personalize } })); }} onCost={addCost} onUnlock={() => voice.current?.unlock()}
      replay={(text, l) => voice.current?.speak(text, l)} /></div>}

    {panel === 'report' && cur && <aside className="report drawer" aria-label="Report">
      <button className="close" aria-label="Close" onClick={() => setPanel(null)}>×</button>
      <div onClick={(e) => { // injected HTML: React's onChange does not see these inputs, clicks do
        if (e.target.id === 'lensToggle') { toggleLens(e.target.checked); return; }
        const b = e.target.closest?.('[data-lever]'); if (b && !busy) applyLever(b.dataset.lever, Number(b.dataset.value)); }}
        dangerouslySetInnerHTML={{ __html: reportHTML }} />
      <YourConditions lang={lang} />
      <div className="drawer-inline"><Assumptions assumptions={tree.assumptions} busy={busy} onApply={(next) => go(path, { assumptions: next, force: true })} /></div>
      <p className="note">{t(lang, 'sessionCost')} USD {cost.toFixed(4)}</p>
    </aside>}

    {started && cur && !busy && !tree.nodes.some((n) => n.status === 'child') && path.length > 0 && !pathReport &&
      <button className="leaf-cta" onClick={() => { setPanel(null); setPathReport(true); }}>
        <span className="leaf-cta-kicker">{t(lang, 'leafEnd')}</span><span>{t(lang, 'openReport')}</span></button>}
    {pathReport && <PathReport lang={lang} tr={(n) => translateNode(n, lang)} profile={profile} startProfile={profile || demoProfile} path={path} assumptions={overrides} lens={lens} weather={weather} onClose={() => setPathReport(false)} />}

    {busy && started && <div className="loading" role="status">{t(lang, 'loading')}</div>}
    {error && <div className="error-toast" role="alert">{error}<button onClick={() => { setError(''); go(path, { force: true }); }}>{t(lang, 'retry')}</button></div>}
  </>;
}

createRoot(document.getElementById('root')).render(<App />);
