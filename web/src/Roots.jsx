import React, { useEffect, useRef, useState } from 'react';
import { apiRequest } from './api.js';
import { profileFields, profileFromForm } from './profile.js';
import { percent } from './results.js';
import Dictation from './Dictation.jsx';

export default function Roots({ profile, busy, onApply, onCost }) {
  const [draft, setDraft] = useState(profile);
  const [edited, setEdited] = useState([]);
  const [text, setText] = useState('');
  const [files, setFiles] = useState([]);
  const [extracting, setExtracting] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const request = useRef(null);
  useEffect(() => { setDraft(profile); setEdited([]); }, [profile]);
  useEffect(() => () => request.current?.abort(), []);

  async function extract(event) {
    event.preventDefault();
    setError(''); setNotice('');
    if (!files.length && !text.trim()) { setError('Add a fictional document or describe a profile first.'); return; }
    if (files.some(file => file.size > 10 * 1024 * 1024)) { setError('Each file must be 10 MB or smaller.'); return; }
    const controller = new AbortController(); request.current = controller;
    const body = new FormData();
    files.forEach(file => body.append('files', file));
    if (text.trim()) body.append('text', text.trim());
    setExtracting(true);
    try {
      const data = await apiRequest('/profiles/extract', { body, signal: controller.signal });
      onCost(data.cost_usd);
      if (!data.profile || typeof data.profile !== 'object') throw new Error('No profile was returned. Please try the questionnaire.');
      // Review partial extraction in the form before it can replace the simulated profile.
      setDraft({ ...profile, ...data.profile, provenance: data.profile.provenance || {} });
      setEdited([]);
      setNotice(data.extractor === 'mock' ? 'Mock extractor: example values returned, not values read from your input. Review the form before applying.'
        : 'Extraction ready. Review the values and their sources, fill any gaps, then apply the profile.');
    } catch (failure) { if (!controller.signal.aborted) setError(failure.message); }
    finally { if (!controller.signal.aborted) setExtracting(false); }
  }
  function apply(event) {
    event.preventDefault(); setError('');
    try { onApply(profileFromForm(draft, draft, edited)); }
    catch (failure) { setError(failure.message); }
  }
  if (!profile) return null;
  return <details className="roots-panel"><summary>Your roots · edit the starting profile</summary>
    <p>Use fictional information only. These fields update the starting point; the demo's decision options, assets, debts and goals remain attached to this profile.</p>
    <div className="roots-grid"><form onSubmit={apply}><fieldset disabled={busy || extracting}><legend>1. Review the starting point</legend>
      <div className="profile-fields">{profileFields.map(field => <label key={field.key}>{field.label}
        <input {...{ type: field.type, min: field.min, step: field.step }} max={field.key === 'age' ? 120 : undefined} required value={draft?.[field.key] ?? ''}
          onChange={event => { setDraft({ ...draft, [field.key]: event.target.value }); setEdited([...new Set([...edited, field.key])]); }} />
        <small>{edited.includes(field.key) ? 'Source: questionnaire edit' : `Source: ${draft?.provenance?.[field.key]?.source || 'demo profile or not supplied'}`}
          {!edited.includes(field.key) && Number.isFinite(draft?.provenance?.[field.key]?.confidence) && ` · extraction confidence ${percent(draft.provenance[field.key].confidence)}`}</small>
      </label>)}</div><p>Income is after social contributions; income tax is handled by the engine's assumptions.</p>
      <button className="primary" type="submit">Apply profile and restart tree</button>
    </fieldset></form>
    <form onSubmit={extract}><fieldset disabled={busy || extracting}><legend>Or start from text, a document or your voice</legend>
      <label>Describe a fictional financial profile<textarea value={text} rows="5" onChange={event => setText(event.target.value)} placeholder="Alexia has CHF 8,000 in savings and pays CHF 900 in monthly rent…" /></label>
      <Dictation disabled={busy || extracting} onText={words => setText(previous => `${previous} ${words}`.trim())} />
      <label>Fictional documents<input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.txt,.csv" onChange={event => setFiles(Array.from(event.target.files))} /></label>
      <small>PDF, images or text · up to 10 MB per file</small>
      <button className="back" type="submit">{extracting ? 'Extracting…' : 'Extract into the form'}</button>
    </fieldset></form></div>
    {notice && <p role="status" className="extraction-notice">{notice}</p>}{error && <p role="alert" className="negative">{error}</p>}
  </details>;
}
