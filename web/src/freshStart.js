// #118: a page load starts clean. The chat, the comparison pins, the personal conditions and the Live consent
// live in sessionStorage so they survive re-renders and lazy chunks, but a reload must not bring them back.
// Imported first in main.jsx, before any store reads its key. Preferences (language, theme, the one-time
// compare hint) are in localStorage and stay; the report-summary cache only saves LLM calls and stays too.
export const KEEP = new Set(['cigala.summary.v1']);

export function freshStart(storage = (() => { try { return globalThis.sessionStorage; } catch { return null; } })()) {
  if (!storage) return [];
  const gone = [];
  try {
    for (let i = storage.length - 1; i >= 0; i--) {
      const k = storage.key(i);
      if (k && k.startsWith('cigala.') && !KEEP.has(k)) gone.push(k);
    }
    gone.forEach((k) => storage.removeItem(k));
  } catch { /* blocked storage: nothing was kept anyway */ }
  return gone;
}

freshStart();
