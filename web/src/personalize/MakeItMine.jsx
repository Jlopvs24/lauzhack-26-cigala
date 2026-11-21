// "Make it mine": the user attaches their own condition to the current branch, in words or by voice.
// Flow: entry pill → text / mic → POST /tree/personalize → a clarifying question, or an editable proposal
// (name, each change in plain words with its amount, mode: this branch vs a new branch) → Confirm stores it
// in the session (personalStore) and calls onConfirm(item, fields) so the scene re-expands and the branch
// re-grows. Proposals from the chat agent arrive as a prop or as a window event (PROPOSAL_EVENT).
import React, { useEffect, useId, useRef, useState } from 'react';
import { requestPersonalization } from './api.js';
import { amountOf, buildItem, describe, normalizeProposal, withAmount } from './model.js';
import { personalStore } from './store.js';
import { pi } from './i18n.js';
import './personalize.css';

export const PROPOSAL_EVENT = 'cigala:personalize-proposal';
const SPEECH = { en: 'en-GB', es: 'es-ES', fr: 'fr-FR', de: 'de-DE' };

function useSpeech(lang, onText) {
  const [listening, setListening] = useState(false);
  const rec = useRef(null), cb = useRef(onText);
  cb.current = onText;
  const R = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null;
  useEffect(() => () => rec.current?.abort?.(), []);
  const toggle = () => {
    if (!R) return;
    if (listening) { rec.current?.stop(); return; }
    const s = new R();
    s.lang = SPEECH[lang] || 'en-GB'; s.interimResults = false; s.continuous = false;
    s.onresult = (e) => { const t = Array.from(e.results).slice(e.resultIndex).map((r) => r[0].transcript).join(' '); if (t) cb.current(t); };
    s.onend = () => setListening(false); s.onerror = () => setListening(false);
    rec.current = s;
    try { s.start(); setListening(true); } catch { setListening(false); }
  };
  return { supported: !!R, listening, toggle };
}

export default function MakeItMine({ lang = 'en', node, path = [], profile = null, assumptions = [], tr = (n) => ({ label: n?.label, desc: n?.description || '' }),
  labelOf = (id) => id, proposal = null, onConfirm, onOpenChange, defaultOpen = false, store = personalStore, request, compact = false }) {
  const L = pi(lang), uid = useId().replace(/:/g, '');
  const [open, setOpen] = useState(defaultOpen);
  const [step, setStep] = useState('ask'); // ask | loading | clarify | proposal | done | error
  const [text, setText] = useState(''), [answer, setAnswer] = useState(''), [history, setHistory] = useState([]);
  const [res, setRes] = useState(null), [draft, setDraft] = useState(null), [error, setError] = useState(''), [fromChat, setFromChat] = useState(false);
  const [doneMsg, setDoneMsg] = useState('');
  const box = useRef(null), first = useRef(null), ac = useRef(null);
  const nodeName = tr(node || {}).label || node?.label || '';
  const speech = useSpeech(lang, (t) => (step === 'clarify' ? setAnswer((a) => (a ? a + ' ' : '') + t) : setText((a) => (a ? a + ' ' : '') + t)));

  const setOpenBoth = (o) => { setOpen(o); onOpenChange?.(o); };
  const reset = () => { ac.current?.abort(); setStep('ask'); setText(''); setAnswer(''); setHistory([]); setRes(null); setDraft(null); setError(''); setFromChat(false); };
  const close = () => { reset(); setOpenBoth(false); };

  const show = (r, chat = false) => {
    setRes(r); setFromChat(chat);
    if (r.status === 'proposal') {
      setDraft({ label: r.proposal.label, mode: r.proposal.mode, interventions: r.proposal.interventions });
      setStep('proposal');
    } else if (r.status === 'clarify') { setAnswer(''); setStep('clarify'); } else { setStep('error'); setError(r.message || L.unsupported); }
  };

  async function submit(t, hist = history) {
    const words = t.trim();
    if (!words || !node) return;
    ac.current?.abort();
    const c = new AbortController(); ac.current = c;
    setStep('loading'); setError('');
    try {
      const r = await requestPersonalization({ profile, path, node, text: words, lang, assumptions, history: hist, tr }, { signal: c.signal, ...(request ? { request } : {}) });
      if (!c.signal.aborted) show(r);
    } catch (e) {
      if (e?.name !== 'AbortError') { setStep('error'); setError(e?.message || L.unsupported); }
    }
  }
  const sendAnswer = () => {
    const a = answer.trim();
    if (!a) return;
    const hist = [...history, { question: res?.question, answer: a }];
    setHistory(hist);
    submit(text.trim() ? `${text.trim()}. ${a}` : a, hist);
  };

  const confirm = () => {
    if (!draft || !res?.proposal) return;
    const taken = store.list().map((i) => i.custom_node?.node_id).filter(Boolean);
    const item = buildItem({ ...res.proposal, interventions: draft.interventions }, { mode: draft.mode, label: draft.label, takenIds: taken, nodeLabel: nodeName });
    store.add(item);
    onConfirm?.(item, store.requestFields());
    setDoneMsg(item.mode === 'branch' ? L.addedBranch(item.label) : L.added(nodeName));
    setStep('done');
    timer.current = setTimeout(() => { reset(); setOpenBoth(false); }, 2600);
  };

  // proposals from the chat: as a prop, or as a window event {proposal | raw answer, node_id?}
  useEffect(() => { if (proposal) { setOpenBoth(true); show(normalizeProposal(proposal, { node_id: node?.node_id, parent_id: node?.parent_id }), true); } }, [proposal]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const on = (e) => {
      const d = e.detail || {};
      if (d.node_id && node?.node_id && d.node_id !== node.node_id) return;
      setOpenBoth(true);
      show(normalizeProposal(d.proposal ? d : d.personalize || d, { node_id: node?.node_id, parent_id: node?.parent_id }), true);
    };
    addEventListener(PROPOSAL_EVENT, on);
    return () => removeEventListener(PROPOSAL_EVENT, on);
  }, [node?.node_id]); // eslint-disable-line react-hooks/exhaustive-deps
  const lastNode = useRef(node?.node_id), timer = useRef(null);
  useEffect(() => { if (lastNode.current !== node?.node_id) { lastNode.current = node?.node_id; reset(); } }, [node?.node_id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => { if (open) first.current?.focus({ preventScroll: true }); }, [open, step]);

  if (!node) return null;
  if (!open) {
    return <button type="button" className={`pz pz-entry ${compact ? 'compact' : ''}`} aria-expanded="false" aria-controls={`pz-${uid}`} onClick={() => setOpenBoth(true)}>
      <span className="pz-plus" aria-hidden="true">+</span><span className="pz-entry-l"><b>{L.entry}</b>{!compact && <small>{L.entrySub}</small>}</span>
    </button>;
  }

  const ivs = draft?.interventions || [];
  return <section className="pz pz-panel" id={`pz-${uid}`} ref={box} aria-label={L.title(nodeName)} onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } }}>
    <header className="pz-head">
      <span className="pz-kicker">{L.entry}</span>
      <button type="button" className="pz-x" aria-label={L.close} onClick={close}>×</button>
    </header>

    {(step === 'ask' || step === 'loading') && <form className="pz-ask" onSubmit={(e) => { e.preventDefault(); submit(text); }}>
      <label htmlFor={`pz-t-${uid}`} className="pz-q">{L.ask(nodeName)}</label>
      <div className="pz-field">
        <textarea id={`pz-t-${uid}`} ref={first} rows={2} value={text} placeholder={L.placeholder} disabled={step === 'loading'}
          onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(text); } }} />
        <button type="button" className={`pz-mic ${speech.listening ? 'on' : ''}`} onClick={speech.toggle} disabled={!speech.supported || step === 'loading'}
          aria-pressed={speech.listening} aria-label={speech.listening ? L.micStop : L.mic} title={speech.supported ? (speech.listening ? L.micStop : L.mic) : L.micNa}>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V21h2v-2.1A7 7 0 0 0 19 12h-2Z" fill="currentColor" /></svg>
        </button>
      </div>
      {speech.listening && <p className="pz-live" role="status">{L.listening}</p>}
      {step === 'ask' && !text && <div className="pz-ex"><span>{L.examples}</span>{L.ex.map((x) => <button type="button" key={x} onClick={() => setText(x)}>{x}</button>)}</div>}
      {step === 'loading' ? <p className="pz-status" role="status"><span className="pz-dots" aria-hidden="true" />{L.reading}</p>
        : <div className="pz-actions"><button type="button" className="pz-btn ghost" onClick={close}>{L.cancel}</button><button type="submit" className="pz-btn primary" disabled={!text.trim()}>{L.check}</button></div>}
    </form>}

    {step === 'clarify' && <form className="pz-ask" onSubmit={(e) => { e.preventDefault(); sendAnswer(); }}>
      {text.trim() && <p className="pz-said">“{text}”</p>}
      <div className="pz-bubble" role="status"><span className="pz-kicker">{L.clarify}</span><p>{res?.question}</p></div>
      <div className="pz-field">
        <input ref={first} aria-label={L.answer} value={answer} placeholder={L.answer} onChange={(e) => setAnswer(e.target.value)} />
        <button type="button" className={`pz-mic ${speech.listening ? 'on' : ''}`} onClick={speech.toggle} disabled={!speech.supported} aria-pressed={speech.listening} aria-label={speech.listening ? L.micStop : L.mic}>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V21h2v-2.1A7 7 0 0 0 19 12h-2Z" fill="currentColor" /></svg>
        </button>
      </div>
      <div className="pz-actions"><button type="button" className="pz-btn ghost" onClick={() => setStep('ask')}>{L.edit}</button><button type="submit" className="pz-btn primary" disabled={!answer.trim()}>{L.send}</button></div>
    </form>}

    {step === 'proposal' && draft && <div className="pz-prop">
      <p className="pz-kicker">{fromChat ? L.fromChat : L.proposal}</p>
      {res?.proposal?.text && <p className="pz-said">“{res.proposal.text}”</p>}
      <label className="pz-lbl" htmlFor={`pz-n-${uid}`}>{L.label}</label>
      <input id={`pz-n-${uid}`} ref={first} className="pz-name" value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })} />
      <p className="pz-lbl" id={`pz-c-${uid}`}>{L.conditions}</p>
      <ul className="pz-conds" aria-labelledby={`pz-c-${uid}`}>
        {ivs.map((iv, i) => {
          const a = amountOf(iv);
          return <li key={i}>
            <span className="pz-cond-t">{describe(iv, lang, labelOf)}</span>
            {a != null && <label className="pz-amt"><span className="sr">{L.amount}</span>CHF
              <input type="number" inputMode="decimal" min="0" step="50" value={a} aria-label={`${L.amount}: ${describe(iv, lang, labelOf)}`}
                onChange={(e) => { const v = parseFloat(e.target.value); setDraft({ ...draft, interventions: ivs.map((x, j) => (j === i ? withAmount(x, Number.isFinite(v) ? v : 0) : x)) }); }} /></label>}
          </li>;
        })}
        {!ivs.length && res?.proposal?.conditions?.map((c, i) => <li key={i}><span className="pz-cond-t">{c}</span></li>)}
      </ul>
      <fieldset className="pz-mode">
        <legend className="pz-lbl">{L.modeTitle}</legend>
        {['patch', 'branch'].map((m) => <label key={m} className={draft.mode === m ? 'on' : ''}>
          <input type="radio" name={`pz-m-${uid}`} value={m} checked={draft.mode === m} onChange={() => setDraft({ ...draft, mode: m })} />
          <span><b>{m === 'patch' ? L.patch : L.branch}</b><small>{m === 'patch' ? L.patchSub : L.branchSub}</small></span>
        </label>)}
      </fieldset>
      <p className="pz-note">{res?.source === 'mock' ? L.mock : L.noNumbers}</p>
      <div className="pz-actions">
        <button type="button" className="pz-btn ghost" onClick={close}>{L.cancel}</button>
        <button type="button" className="pz-btn ghost" onClick={() => { setText(res?.proposal?.text || text); setStep('ask'); }}>{L.edit}</button>
        <button type="button" className="pz-btn primary" onClick={confirm} disabled={!ivs.length || !draft.label.trim()}>{L.confirm}</button>
      </div>
    </div>}

    {step === 'done' && <p className="pz-done" role="status" ref={first} tabIndex={-1}><span aria-hidden="true">✓</span>{doneMsg}</p>}

    {step === 'error' && <div className="pz-ask" role="alert">
      <p className="pz-err">{error}</p>
      <div className="pz-actions"><button type="button" className="pz-btn ghost" onClick={close}>{L.cancel}</button><button type="button" ref={first} className="pz-btn primary" onClick={() => setStep('ask')}>{L.retry}</button></div>
    </div>}
  </section>;
}
