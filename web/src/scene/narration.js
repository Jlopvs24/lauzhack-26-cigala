// What Lumi says about a node, from engine numbers only (no LLM), and the memory that keeps it from
// re-reading a bubble it already spoke.
import { STORY, NODES, UI } from './i18n.js';
import { planCheck } from './headline.js';

// Node text in the UI language; `known` = false when we only have the engine's English text.
// The description is translated only while the engine's English text still matches the table.
export function translateNode(n, lang) {
  if (lang === 'en') return { label: n.label, desc: n.description || '', known: true, descKnown: true };
  const row = NODES[n.label], x = row?.[lang];
  if (!x) return { label: n.label, desc: n.description || '', known: false, descKnown: false };
  const same = !n.description || row.en?.[1] === n.description;
  return { label: x[0], desc: same ? x[1] : n.description || '', known: true, descKnown: same };
}

// The opening Lumi says when arriving at a node (its name and description), as storyFor builds it:
// what the voice prefetches for the children while the user is still reading.
export function openingFor(n, lang) {
  const c = translateNode(n, lang);
  if (!c.known) return '';
  return `${c.label}. ${c.descKnown ? c.desc.replace(/([^.])$/, '$1.') : ''}`.trim();
}

export function storyFor(data, lang, who = 'Alexia') {
  const S = STORY[lang] || STORY.en;
  const cur = data.nodes.find((n) => n.node_id === data.current);
  const m = cur.result?.metrics || {}, h = cur.result?.health || {};
  const cash = m.first_negative_month != null ? S.short(m.first_negative_month + 1) : S.ok;
  const c = translateNode(cur, lang);
  // say only what we can say in this language (unknown engine text stays on screen, not in the voice)
  const kids = data.nodes.filter((n) => n.status === 'child').map((n) => translateNode(n, lang)).filter((x) => x.known).map((x) => x.label);
  const n = { who, label: c.known ? c.label : '', desc: c.known && c.descKnown ? c.desc.replace(/([^.])$/, '$1.') : '', score: Math.round(h.score ?? 0), check: (planCheck(cur.result, lang)?.label || '').replace(/^./, (x) => x.toLowerCase()) };
  if (data.current === '0') return S.root(n, cash, kids);
  const dh = cur.delta_vs_parent?.health_score;
  return S.node(n, cash, kids, dh == null ? '' : S.delta(dh)).replace(/^\. /, '');
}

// Returns {text, speak}: the bubble text and what to say aloud. A node already narrated in this
// language (and profile) shows its bubble again but only says "Back at …".
// bubbles stay short (3 sentences): what it is, the key numbers, the closing invitation to choose
export function brief(text) {
  const p = String(text || '').split(/(?<=[.!?…])\s+/).filter(Boolean);
  if (p.length <= 3) return text;
  const mid = p.slice(1, -1).find((x) => /\d/.test(x)) || p[1]; // the sentence with the numbers that matter
  return [p[0], mid, p.at(-1)].join(' ');
}

export function createNarrator() {
  const done = new Set();
  return {
    next(data, lang, profileKey = 'demo', who) {
      const text = brief(storyFor(data, lang, who));
      const key = `${lang}|${profileKey}|${data.current}`;
      if (!done.has(key)) { done.add(key); return { text, speak: text, revisit: false }; }
      const cur = data.nodes.find((n) => n.node_id === data.current), c = translateNode(cur, lang);
      const S = STORY[lang] || STORY.en;
      return { text, speak: c.known ? S.back(c.label.replace(/^./, (x) => x.toLowerCase())) : '', revisit: true };
    },
    reset() { done.clear(); },
  };
}

export const t = (lang, key) => (UI[lang] || UI.en)[key] ?? UI.en[key];
