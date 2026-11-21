// "Your conditions": the session's own conditions with a remove button each. Custom branches are marked.
import React, { useEffect, useState } from 'react';
import { describe } from './model.js';
import { personalStore } from './store.js';
import { pi } from './i18n.js';
import './personalize.css';

export function usePersonalItems(store = personalStore) {
  const [items, setItems] = useState(() => store.list());
  useEffect(() => { setItems(store.list()); return store.subscribe(setItems); }, [store]);
  return items;
}

export default function YourConditions({ lang = 'en', store = personalStore, onChange, labelOf = (id) => id, nodeName = (item) => item.node_label || item.node_id, hideEmpty = true }) {
  const L = pi(lang), items = usePersonalItems(store);
  if (!items.length) return hideEmpty ? null : <p className="pz pz-empty">{L.empty}</p>;
  return <section className="pz pz-list" aria-label={L.listTitle}>
    <h3>{L.listTitle} <span className="pz-count">{items.length}</span></h3>
    <ul>
      {items.map((it) => <li key={it.id} className={it.mode}>
        <span className={`pz-badge ${it.mode}`}>{it.mode === 'branch' ? L.newBranch : L.onBranch}</span>
        <span className="pz-li-t">
          <b>{it.label}</b>
          <small>{it.mode === 'patch' ? `${nodeName(it)} · ` : ''}{(it.interventions || []).map((iv) => describe(iv, lang, labelOf)).join(' · ')}</small>
        </span>
        <button type="button" className="pz-rm" aria-label={L.remove(it.label)} title={L.remove(it.label)} onClick={() => { store.remove(it.id); onChange?.(store.list(), store.requestFields()); }}>×</button>
      </li>)}
    </ul>
  </section>;
}
