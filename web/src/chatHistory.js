// Conversation with Lumi, kept for the whole browser session (survives node, language and
// assumption changes, and reloads of the tab). Storage may be unavailable (private mode,
// blocked site data): the history then lives in memory only and the chat still works.

export const HISTORY_KEY = 'cigala.chat.v1';
export const MAX_MESSAGES = 60; // older turns are dropped from the panel
export const API_TURNS = 10; // turns sent to /agent/ask as context

function safeStorage(storage) {
  try {
    const s = storage === undefined ? globalThis.sessionStorage : storage;
    if (!s) return null;
    const probe = '__cigala_probe__';
    s.setItem(probe, '1'); s.removeItem(probe);
    return s;
  } catch { return null; }
}

function clean(list) {
  return (Array.isArray(list) ? list : [])
    .filter((m) => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string' && m.content)
    .slice(-MAX_MESSAGES);
}

export function createHistory({ storage, key = HISTORY_KEY } = {}) {
  const store = safeStorage(storage);
  let messages = [];
  try { messages = clean(JSON.parse(store?.getItem(key) || '[]')); } catch { messages = []; }
  const listeners = new Set();
  const persist = () => {
    try { store?.setItem(key, JSON.stringify(messages)); } catch { /* quota or blocked: keep in memory */ }
    for (const fn of listeners) fn(messages);
  };
  return {
    all: () => messages,
    // meta: what the UI shows under an answer (mode, cost, latency, sources, node); never sent back to the API
    append(role, content, meta = undefined) {
      const msg = { role, content: String(content), at: Date.now(), ...(meta ? { meta } : {}) };
      messages = clean([...messages, msg]);
      persist();
      return msg;
    },
    clear() { messages = []; persist(); },
    forApi(turns = API_TURNS) { return messages.slice(-turns).map(({ role, content }) => ({ role, content })); },
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    persistent: !!store,
  };
}
