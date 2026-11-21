import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { pathToNode, validateTree } from './tree.js';
import NodeDetail from './NodeDetail.jsx';
import { money } from './results.js';
import './style.css';

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

function Branch({ node, current, busy, onChoose }) {
  const metrics = node.result.metrics;
  const selected = node.node_id === current;
  return <button className={`branch ${node.status} ${selected ? 'current' : ''}`}
    disabled={busy || selected} aria-current={selected ? 'step' : undefined}
    onClick={() => onChoose(node.node_id)}>
    <span className="branch-top"><span className="branch-dot" />
      {selected ? 'Your current branch' : node.status === 'sibling' ? 'Alternative path' : 'Explore this option'}
      <span className="arrow" aria-hidden="true">↗</span></span>
    <h3>{node.label}</h3>
    <dl className="metrics">
      <div><dt>Median final net worth</dt><dd>{money(metrics.final_net_worth_p50)}</dd></div>
      <div><dt>Lowest cash balance</dt><dd className={metrics.min_cash < 0 ? 'negative' : ''}>{money(metrics.min_cash)}</dd></div>
    </dl>
    <span className={`cash-note ${metrics.first_negative_month != null ? 'warning' : ''}`}>
      {metrics.first_negative_month != null
        ? `Financing needed from month ${metrics.first_negative_month + 1}`
        : 'No negative cash in this simulation'}</span>
  </button>;
}

function App() {
  const [tree, setTree] = useState(null);
  const [profile, setProfile] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [overrides, setOverrides] = useState([]);
  const [retryRequest, setRetryRequest] = useState({ path: [], assumptions: [] });
  const controller = useRef(null);
  const heading = useRef(null);

  async function expand(path, moveFocus = true, assumptions = overrides) {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setBusy(true);
    setError('');
    setRetryRequest({ path, assumptions });
    try {
      const response = await fetch(`${apiBase}/tree/expand`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, assumptions }), signal: request.signal,
      });
      if (!response.ok) throw new Error(`The simulation API returned ${response.status}. Check the backend and retry.`);
      const data = validateTree(await response.json());
      if (request.signal.aborted) return;
      setTree(data);
      setOverrides(assumptions);
      if (moveFocus) requestAnimationFrame(() => heading.current?.focus());
    } catch (failure) {
      if (!request.signal.aborted) setError(failure instanceof TypeError
        ? 'Cannot reach the simulation API. Start the backend on port 8000, then retry.' : failure.message);
    } finally {
      if (!request.signal.aborted) setBusy(false);
    }
  }

  useEffect(() => {
    expand([], false);
    const profileRequest = new AbortController();
    fetch(`${apiBase}/profiles/demo`, { signal: profileRequest.signal })
      .then(response => response.ok ? response.json() : null)
      .then(data => { if (!profileRequest.signal.aborted) setProfile(data?.profile || null); })
      .catch(() => {}); // The tree remains usable if optional profile details are unavailable.
    return () => { controller.current?.abort(); profileRequest.abort(); };
  }, []);

  function choose(id) {
    try { expand(pathToNode(tree.nodes, id)); }
    catch (failure) { setError(failure.message); }
  }

  const chosen = tree?.nodes.filter(node => node.status === 'chosen') || [];
  const alternatives = tree?.nodes.filter(node => node.status === 'sibling') || [];
  const children = tree?.nodes.filter(node => node.status === 'child') || [];
  const current = tree?.nodes.find(node => node.node_id === tree.current);
  const path = tree ? pathToNode(tree.nodes, tree.current) : [];
  const mock = tree?.engine === 'mock';

  return <div className="app">
    <header className="header"><a className="brand" href="/" aria-label="cigala home"><span aria-hidden="true">✳</span> cigala<span className="brand-period">.</span></a>
      <span className="header-note">A little clarity. Room to grow.</span>
      <span className="demo-label">FICTIONAL DEMO</span></header>
    <main>
      <section className="intro"><div><p className="eyebrow">YOUR TREE OF POSSIBILITIES</p>
        <h1>One choice.<br /><em>Room for many futures.</em></h1>
        <p className="intro-text">Explore how life's decisions shape your finances.<br />Follow a branch, compare the trade-offs, and change your mind.</p></div>
        <aside className="profile"><span className="profile-icon" aria-hidden="true">A</span>
          <div><span className="eyebrow">MEET YOUR STARTING POINT</span><h2>{profile?.display_name || 'Alexia'}'s story</h2>
            <p>{profile ? `${profile.age} years old · ${profile.city}` : 'Fictional student · Lausanne'}</p></div>
          {profile && <dl><div><dt>Starting cash</dt><dd>{money(profile.cash)}</dd></div>
            <div><dt>Monthly net income</dt><dd>{money(profile.monthly_net_income)}</dd></div></dl>}
        </aside></section>

      <section className="workspace" aria-labelledby="tree-heading" aria-busy={busy}>
        <div className="workspace-heading"><div><p className="eyebrow">EXPLORE, ONE STEP AT A TIME</p>
          <h2 id="tree-heading" tabIndex="-1" ref={heading}>{path.length ? 'Your path is taking shape.' : 'Where would you like to grow?'}</h2></div>
          <button className="back" disabled={busy || !path.length} onClick={() => expand(path.slice(0, -1))}>← Back one step</button></div>
        <div role="status" className="status">{busy ? 'Calculating the visible branches…' : tree
          ? `${tree.nodes.length} visible nodes · ${current?.result.horizon_months ?? '—'}-month horizon · ${mock ? 'Mock engine — illustrative results' : 'Simulation results'}`
          : 'Connect the simulation API to start exploring.'}</div>
        {error && <div className="error" role="alert"><p>{error}</p><button onClick={() => expand(retryRequest.path, true, retryRequest.assumptions)} disabled={busy}>Retry simulation</button></div>}

        {tree && <div className="tree">
          <nav className="path" aria-label="Chosen decision path">{chosen.filter(node => node.node_id !== tree.current).map((node, index) =>
            <React.Fragment key={node.node_id}><button disabled={busy} onClick={() => choose(node.node_id)}>
              <span className="path-number">{index === 0 ? '○' : index}</span>{node.label}</button><span className="path-connector" aria-hidden="true" /></React.Fragment>)}</nav>
          {current && <div className="current-row"><Branch node={current} current={tree.current} busy={busy} onChoose={choose} /></div>}
          {!!alternatives.length && <details className="alternatives" open><summary>Other paths at this decision · {alternatives.length}</summary>
            <div className="alternative-grid">{alternatives.map(node => <Branch key={node.node_id} node={node} current={tree.current} busy={busy} onChoose={choose} />)}</div></details>}
          {!!children.length && <><div className="growth-line" aria-hidden="true" /><p className="next-label">{path.length ? 'WHAT HAPPENS NEXT? PICK A BRANCH.' : 'THREE WAYS TO BEGIN. YOU CAN ALWAYS GO BACK.'}</p>
            <div className="children">{children.map(node => <Branch key={node.node_id} node={node} current={tree.current} busy={busy} onChoose={choose} />)}</div></>}
          {!children.length && <p className="leaf-note">You've reached the end of this branch. Go back to explore an alternative.</p>}
          <div className="roots" aria-hidden="true">╲ │ ╱</div>
        </div>}
      </section>
      {current && <NodeDetail node={current} peers={alternatives.length ? [current, ...alternatives] : [current, ...children]}
        assumptions={tree.assumptions} busy={busy} onApply={next => expand(path, false, next)} />}
      <footer><p><strong>Possibilities, with perspective.</strong> These are conditional simulations, not guaranteed forecasts. {mock && 'The engine currently uses mock assumptions.'}</p>
        <p>Only visible branches are calculated. Your choices stay in this session.</p></footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
