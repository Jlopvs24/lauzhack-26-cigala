// Dev-only harness: real /tree/expand data rendered as scene-like cards with the compare strip and pins,
// the "compare these options" button, the sticky bar and the comparison page. Not in the build.
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import '../app.css';
import { apiRequest } from '../api.js';
import { translateNode } from '../scene/narration.js';
import { cardHeadline } from '../scene/headline.js';
import { CardCompareStrip, CompareOptionsButton, CompareRoot, pinHTML, AddToCompare } from './index.js';

const q = new URLSearchParams(location.search);
const lang = q.get('lang') || 'en';
if (q.get('theme')) document.documentElement.dataset.theme = q.get('theme');
const path = (q.get('path') || '2').split(',').filter(Boolean);
const tr = (n) => translateNode(n, lang);

function Demo() {
  const [tree, setTree] = useState(null);
  useEffect(() => { apiRequest('/tree/expand', { body: { path } }).then(setTree); }, []);
  if (!tree) return <p style={{ padding: 20 }}>Loading…</p>;
  const cards = tree.nodes.filter((n) => n.status === 'child' || n.status === 'sibling');
  const chosen = tree.path.filter((id) => id !== '0');
  return <div className="stage">
    <h1>{tr(tree.nodes.find((n) => n.node_id === tree.current)).label}</h1>
    <div className="demo-bar"><CompareOptionsButton tree={tree} lang={lang} />
      <AddToCompare path={chosen} label={tr(tree.nodes.find((n) => n.node_id === tree.current)).label} lang={lang} /></div>
    {cards.map((n) => {
      const h = cardHeadline(n.result, lang);
      const p = n.status === 'child' ? [...chosen, n.node_id] : [...chosen.slice(0, -1), n.node_id];
      return <div key={n.node_id} className={`tag ${n.status}`} style={{ position: 'relative', transform: 'none' }}>
        <span className="card" style={{ position: 'relative' }}>
          <span className="name">{tr(n).label}</span>
          <span className="meta">{h?.a && <span className={`slot-a ${h.a.kind}`}>{h.a.text}</span>}
            <CardCompareStrip node={n} siblings={tree.nodes} lang={lang} tr={tr} /></span>
          <span style={{ position: 'absolute', top: 8, right: 8 }} dangerouslySetInnerHTML={{ __html: pinHTML(p, tr(n).label, lang) }} />
        </span>
      </div>;
    })}
    <CompareRoot lang={lang} tr={tr} />
  </div>;
}
createRoot(document.getElementById('root')).render(<Demo />);
