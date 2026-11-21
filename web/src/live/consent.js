// Lumi Live consent (#103 item 5): Live sends the user's voice to Google, so the call only connects after
// an explicit "Start", remembered for this browser session (sessionStorage; memory when it is blocked).
export const CONSENT_KEY = 'cigala.live.consent.v1';

const memory = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) }; };
const defaultStorage = () => { try { if (typeof sessionStorage !== 'undefined') return sessionStorage; } catch { /* blocked */ } return memory(); };

export function createConsent(storage = defaultStorage()) {
  let mem = false; // when storage throws, the choice still holds for this page
  return {
    given() { try { return storage.getItem(CONSENT_KEY) === '1' || mem; } catch { return mem; } },
    give() { mem = true; try { storage.setItem(CONSENT_KEY, '1'); } catch { /* memory only */ } },
    reset() { mem = false; try { storage.removeItem(CONSENT_KEY); } catch { /* nothing */ } },
  };
}

export const liveConsent = createConsent();
