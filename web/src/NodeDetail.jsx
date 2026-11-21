import React, { useEffect, useState } from 'react';
import { money, percent, bandGeometry, strongestSensitivity, assumptionOverrides, healthFraction } from './results.js';

function BandChart({ result }) {
  const bands = result.bands?.net_worth;
  const chart = bandGeometry(bands);
  if (!chart) return <p>Uncertainty bands are not available for this result.</p>;
  return <figure className="band-chart">
    <svg viewBox="0 0 700 280" role="img" aria-label={`Net worth over ${result.horizon_months} months: median line and p10 to p90 range. Final median ${money(bands.p50.at(-1))}.`}>
      <line x1="76" x2="676" y1={chart.zeroY} y2={chart.zeroY} stroke="#b5bfac" strokeDasharray="4 4" />
      <polygon points={chart.area} fill="#dce8cd" />
      <polyline points={chart.median} fill="none" stroke="#426945" strokeWidth="3" />
      <text x="4" y="32">{money(chart.high)}</text><text x="4" y="232">{money(chart.low)}</text>
      <text x="76" y="260">Today</text><text x="590" y="260">Month {result.horizon_months}</text>
    </svg>
    <figcaption><span className="legend-band" />p10–p90 range <span className="legend-line" />p50 (median)
      <p>80% of simulated paths fall inside this range at each month, under the model's assumptions. It is not a guarantee for your life or a range containing 80% of whole paths.</p></figcaption>
    <dl className="final-bands">{['p10', 'p50', 'p90'].map(key => <div key={key}><dt>Final {key}</dt><dd>{money(bands[key].at(-1))}</dd></div>)}</dl>
  </figure>;
}

export function Assumptions({ assumptions = [], busy, onApply }) {
  const [values, setValues] = useState({});
  const [error, setError] = useState('');
  useEffect(() => { setValues(Object.fromEntries(assumptions.map(item => [item.id, item.value]))); setError(''); }, [assumptions]);
  function submit(event) {
    event.preventDefault();
    try { const next = assumptionOverrides(assumptions, values); setError(''); onApply(next); }
    catch (failure) { setError(failure.message); }
  }
  return <details className="assumptions-panel"><summary>Inspect and edit the assumptions</summary>
    <p>Changes recalculate every visible branch. Rates use decimals: 0.05 means 5%.</p>
    <form onSubmit={submit}><fieldset disabled={busy}><legend className="sr-only">Financial assumptions</legend>
      <div className="assumption-grid">{assumptions.map(item => <label className="assumption" key={item.id}>
        <span>{item.label || (item.param || item.id).replaceAll('_', ' ')} <small>{item.unit}</small></span>
        <input type="number" step="any" required aria-label={item.param || item.id} disabled={!item.editable}
          value={values[item.id] ?? ''} onChange={event => setValues({ ...values, [item.id]: event.target.value })} />
        <small>{item.kind || 'assumption'} · {item.source || 'Source not supplied'}{item.retrieved && ` · retrieved ${item.retrieved}`}</small>
        {item.range && <small>Sensitivity range: {item.range.join(' to ')} (not a hard input limit)</small>}
        {item.verified === false && <small>Source or modelling choice not verified by the team.</small>}
      </label>)}</div>
      {error && <p role="alert" className="negative">{error}</p>}
      <div className="form-actions"><button type="submit" className="primary" disabled={!assumptions.length}>Apply and recalculate</button>
        <button type="button" className="back" onClick={() => onApply([])}>Reset to engine defaults</button></div>
    </fieldset></form>
  </details>;
}

export default function NodeDetail({ node, peers, assumptions, busy, onApply }) {
  const result = node.result;
  const sensitivity = strongestSensitivity(result.sensitivity);
  const sensitiveAssumption = assumptions?.find(item => item.id === sensitivity?.assumption_id);
  const score = healthFraction(result.health);
  const goals = Object.entries(result.metrics.goal_probability || {});
  return <section className="node-detail" aria-labelledby="detail-heading" aria-busy={busy}>
    <div className="detail-heading"><div><p className="eyebrow">LOOK A LITTLE CLOSER</p><h2 id="detail-heading">{node.label}</h2></div>
      <span className="detail-meta">{result.n_paths?.toLocaleString()} simulated paths · seed {result.seed}</span></div>
    {node.description && <p>{node.description}</p>}
    {!!node.changes?.length && <details className="node-changes"><summary>What changed from the previous decision?</summary><ul>{node.changes.map((change, i) => <li key={i}>{change}</li>)}</ul></details>}
    <div className="detail-grid"><div className="detail-main"><h3>How net worth could evolve</h3><BandChart result={result} />
      <div className="comparison"><h3>Compare the trade-offs</h3><p>Alternatives at the same decision. All use the same assumptions and horizon.</p>
        <div className="table-scroll" tabIndex="0" role="region" aria-label="Scenario comparison"><table><thead><tr><th scope="col">Scenario</th><th scope="col">Final median net worth</th><th scope="col">Lowest cash</th><th scope="col">Financing needed</th></tr></thead>
          <tbody>{peers.map(peer => <tr key={peer.node_id} className={peer.node_id === node.node_id ? 'selected-row' : ''}>
            <th scope="row">{peer.label}{peer.node_id === node.node_id && <small>Current branch</small>}</th>
            <td>{money(peer.result.metrics.final_net_worth_p50)}</td><td>{money(peer.result.metrics.min_cash)}</td>
            <td>{peer.result.metrics.first_negative_month == null ? 'Not in this simulation' : `Month ${peer.result.metrics.first_negative_month + 1}`}</td>
          </tr>)}</tbody></table></div></div>
    </div><aside className="detail-sidebar"><div className="health-card"><p className="eyebrow">FINANCIAL HEALTH INDICATOR</p>
      {Number.isFinite(score) ? <><strong>{percent(score)}</strong><meter min="0" max="1" value={score} aria-label="Financial health indicator" />
        <dl>{Object.entries(result.health.components || {}).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{percent(typeof value === 'object' ? value.score : value)}</dd></div>)}</dl>
        {result.health.method && <details><summary>How this indicator is calculated</summary><p>{result.health.method}</p>{Object.entries(result.health.components).map(([name, component]) =>
          <p key={name}><strong>{name} · weight {percent(component.weight)}</strong><br />{component.explanation}</p>)}</details>}
      </> : <p>Not available</p>}
      <p>Model-defined indicator, not a rating of your life choices.</p></div>
      <div className="insight-card"><h3>The assumption that matters most</h3>{sensitivity ? <p>
        <strong>{sensitivity.label || (sensitiveAssumption?.param || sensitivity.assumption_id).replaceAll('_', ' ')}</strong>: {Number.isFinite(sensitivity.low_value) && Number.isFinite(sensitivity.high_value)
          ? <>moving from {sensitivity.low_value} to {sensitivity.high_value} {sensitivity.unit} changes the sensitivity run's mean final net worth from {money(sensitivity.final_net_worth_low)} to {money(sensitivity.final_net_worth_high)}.</>
          : <>changing it{sensitivity.change ? ` by ${sensitivity.change}` : ''} changes final deterministic net worth by <strong>{money(sensitivity.delta_final_net_worth)}</strong>.</>}</p>
        : <p>The engine has not reported a sensitivity result for this branch.</p>}</div>
      {!!goals.length && <div className="insight-card"><h3>Goals under these assumptions</h3><dl>{goals.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{percent(value)} of simulated paths</dd></div>)}</dl></div>}
      <div className="guide-space"><span aria-hidden="true">✳</span><h3>A little perspective</h3><p>{result.metrics.first_negative_month == null
        ? 'This branch keeps cash above zero in the deterministic calculation. Compare its goals and uncertainty with the alternatives.'
        : `The deterministic calculation needs financing from month ${result.metrics.first_negative_month + 1}. A positive final net worth does not remove that earlier cash shortfall.`}</p></div>
    </aside></div>
    <Assumptions assumptions={assumptions} busy={busy} onApply={onApply} />
    <details className="calculation-checks"><summary>Calculation checks and trace</summary><ul>{(result.checks || []).map(check => <li key={check.name}>
      {check.passed ? 'Passed' : 'Failed'} · {check.name.replaceAll('_', ' ')}{check.detail && ` — ${check.detail}`}</li>)}</ul><code>{result.trace_id}</code></details>
  </section>;
}
