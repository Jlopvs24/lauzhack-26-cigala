// Mountable pieces of the comparison (web/src/compare, owner thread 10). Mount guide: README.md.
import React, { lazy, Suspense, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { cardCompareHTML, optionPaths, pathKey } from './model.js';
import { compareStore, openCompare, COMPARE_OPEN, currentWeather } from './store.js';
import { ci } from './i18n.js';
import { personalFields, personalStore, validPath } from '../personalize/store.js';
import './compare.css';

const ComparePage = lazy(() => import('./ComparePage.jsx'));
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const labelFn = (tr) => (id, label) => (tr ? tr({ node_id: id, label }).label || label : label);

export function useCompareItems() {
  return useSyncExternalStore((fn) => compareStore.subscribe(fn), compareStore.list, compareStore.list);
}
/** Inside each option card: where this option sits among its siblings + 1–2 delta chips. */
export function CardCompareStrip({ node, siblings, metric = 'final_net_worth_real', lang = 'en', tr, compact = false }) {
  const html = useMemo(() => cardCompareHTML(node, siblings, { lang, metric, compact, label: labelFn(tr) }), [node, siblings, lang, metric, compact, tr]);
  return html ? <span className="ccs-host" dangerouslySetInnerHTML={{ __html: html }} /> : null;
}

/** "+ Add to comparison" (report header, leaf cards). `path` from the root, "0" optional. */
export function AddToCompare({ path, label, crumbs, lang = 'en', variant = 'pill' }) {
  const L = ci(lang);
  const items = useCompareItems();
  const on = items.some((i) => i.key === pathKey(path || []));
  const full = !on && items.length >= compareStore.max;
  const btn = <button type="button" className={`cmp-add ${variant} ${on ? 'on' : ''}`} aria-pressed={on} disabled={full}
    title={full ? L.full : on ? L.unpin(label) : L.pin(label)} aria-label={full ? L.full : on ? L.unpin(label) : L.pin(label)}
    onClick={(e) => { e.stopPropagation(); compareStore.toggle({ path, label, crumbs }); }}>
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">{on
      ? <path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      : <path d="M8 3v10M3 8h10" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />}</svg>
    {variant !== 'icon' && <span>{on ? L.added : L.add}</span>}
  </button>;
  if (variant === 'icon' || !on) return btn;
  // added: say so, and offer the comparison right here (it opens over the report)
  return <span className="cmp-add-group" role="group">{btn}
    <button type="button" className="cmp-add-go" onClick={(e) => { e.stopPropagation(); openCompare(); }}>
      {items.length < 2 ? L.withAlternatives : L.compareN(items.length)}<span aria-hidden="true"> →</span></button>
    <span className="cmp-sr" aria-live="polite">{L.addedLive(items.length, compareStore.max)}</span></span>;
}

/** The same "+" as an HTML string for the scene's cards (handled by <CompareRoot/>'s click delegate). */
export function pinHTML(path, label, lang = 'en') {
  const L = ci(lang), key = pathKey(path || []), on = compareStore.has(path || []);
  const full = !on && compareStore.full();
  return `<button type="button" class="cmp-pin${on ? ' on' : ''}" data-compare-path="${esc(key)}" data-compare-label="${esc(label)}" aria-pressed="${on}"${full ? ' disabled' : ''} aria-label="${esc(full ? L.full : on ? L.unpin(label) : L.pin(label))}" title="${esc(full ? L.full : on ? L.unpin(label) : L.pin(label))}">${on ? '✓' : '+'}</button>`;
}

/** One click: compare the options visible here (children of the current node, or it and its siblings). */
export function CompareOptionsButton({ tree, lang = 'en', className = 'cmp-options-btn' }) {
  const L = ci(lang), paths = optionPaths(tree);
  if (paths.length < 2) return null;
  return <button type="button" className={className} onClick={() => openCompare({ paths })}>
    <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><path d="M3 13V7M8 13V3M13 13V9" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
    <span>{L.compareOptions}</span></button>;
}

/** Sticky bar: "2 of 4 selected · Compare", removable chips. */
export function CompareBar({ lang = 'en', tr, hidden = false }) {
  const L = ci(lang), items = useCompareItems(), label = labelFn(tr);
  if (hidden || !items.length) return null;
  return <div className="cmp-bar" role="region" aria-label={L.title}>
    <span className="cmp-bar-count" aria-live="polite">{L.barCount(items.length, compareStore.max)}</span>
    <ul className="cmp-bar-chips">{items.map((i, k) => <li key={i.key} className={`s${k + 1}`}>
      <i className="cmp-swatch" aria-hidden="true" /><span>{label(i.path.at(-1), i.label)}</span>
      <button type="button" aria-label={L.remove(label(i.path.at(-1), i.label))} onClick={() => compareStore.remove(i.key)}>×</button></li>)}</ul>
    <div className="cmp-bar-actions">
      <button type="button" className="cmp-bar-clear" onClick={() => compareStore.clear()}>{L.clear}</button>
      <button type="button" className="cmp-bar-go" onClick={() => openCompare()}>{items.length < 2 ? L.withAlternatives : L.compare}<i className="cmp-bar-n" aria-hidden="true">{items.length}</i></button>
    </div>
  </div>;
}

const HINT_KEY = 'cigala.compare.hint.v1';
const hintSeen = () => { try { return localStorage.getItem(HINT_KEY) === '1'; } catch { return false; } };
const markHint = () => { try { localStorage.setItem(HINT_KEY, '1'); } catch { /* private mode */ } };

/** First use (#103): one line on how comparing works, until dismissed or the first + is used. */
export function CompareHint({ lang = 'en', hidden = false }) {
  const L = ci(lang), items = useCompareItems();
  const [seen, setSeen] = useState(hintSeen);
  useEffect(() => { if (items.length && !seen) { markHint(); setSeen(true); } }, [items.length, seen]);
  if (hidden || seen || items.length) return null;
  return <div className="cmp-hint" role="note">
    <span className="cmp-hint-plus" aria-hidden="true">+</span><span>{L.firstHint}</span>
    <button type="button" onClick={() => { markHint(); setSeen(true); }}>{L.hintClose}</button>
  </div>;
}

/**
 * Mount once in the app shell. Renders the sticky bar and, when opened (openCompare / the bar / the
 * options button), the comparison page. Also handles `+` pins inside the scene's HTML cards.
 * `weather` defaults to the latest one from web/src/weather; personal conditions come from web/src/personalize.
 */
export function CompareRoot({ lang = 'en', tr, profile = null, assumptions = [], weather, showBar = true }) {
  const [open, setOpen] = useState(null); // {paths, source}
  const items = useCompareItems();
  useEffect(() => {
    const onOpen = (e) => setOpen({ paths: e.detail?.paths || null, source: e.detail?.source || 'pinned' });
    // pins in HTML cards: capture phase, so the card under the button does not navigate
    const onClick = (e) => {
      const b = e.target.closest?.('[data-compare-path]');
      if (!b) return;
      e.stopPropagation(); e.preventDefault();
      const path = b.dataset.comparePath === '0' ? [] : b.dataset.comparePath.split('/');
      const on = compareStore.toggle({ path, label: b.dataset.compareLabel || '' });
      b.classList.toggle('on', !!on); b.setAttribute('aria-pressed', String(!!on)); b.textContent = on ? '✓' : '+';
    };
    addEventListener(COMPARE_OPEN, onOpen);
    document.addEventListener('click', onClick, true);
    // a removed personal branch takes its pinned paths with it
    const unsub = personalStore.subscribe(() => compareStore.prune((p) => validPath(p, personalStore).length === p.length));
    return () => { removeEventListener(COMPARE_OPEN, onOpen); document.removeEventListener('click', onClick, true); unsub(); };
  }, []);
  const paths = open ? (open.paths || items.map((i) => i.path)) : null;
  return <>
    {showBar && <CompareBar lang={lang} tr={tr} hidden={!!open} />}
    {showBar && <CompareHint lang={lang} hidden={!!open} />}
    {open && <Suspense fallback={null}>
      <ComparePage lang={lang} tr={tr} paths={paths} source={open.source} profile={profile} assumptions={assumptions}
        weather={weather ?? currentWeather()} fields={personalFields()} onClose={() => setOpen(null)}
        onRemove={(key) => { if (open.source === 'pinned') compareStore.remove(key); else setOpen((o) => ({ ...o, paths: o.paths.filter((p) => pathKey(p) !== key) })); }} />
    </Suspense>}
  </>;
}

export { openCompare };
