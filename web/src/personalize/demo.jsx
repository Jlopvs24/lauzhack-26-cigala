// Dev-only harness for "Make it mine": the component on a branch, the list, and chat-style proposals.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { MakeItMine, YourConditions, PROPOSAL_EVENT, personalStore, buildItem } from './index.js';
import { mockPersonalize } from './model.js';
import { translateNode } from '../scene/narration.js';

const q = new URLSearchParams(location.search);
const lang = q.get('lang') || 'en', state = q.get('state') || 'entry';
if (q.get('theme')) document.documentElement.dataset.theme = q.get('theme');
if (q.get('app') === '1') import('../app.css');
const node = { node_id: '2', parent_id: '0', label: "Do a master's", description: 'Two years of master\'s with a student job, then a better-paid job.' };
const tr = (n) => translateNode(n, lang);
if (q.get('seed') === '1' && !personalStore.list().length) {
  const iv = { param: 'monthly_net_income', op: 'add', value: 600, from_month: 0, to_month: 24, label: 'Scholarship' };
  personalStore.add(buildItem({ id: 'demo-a', mode: 'patch', node_id: '2', interventions: [iv], label: 'CHF 600/month scholarship', text: "I'd get a CHF 600/month scholarship" }, { nodeLabel: tr(node).label }));
  personalStore.add(buildItem({ id: 'demo-b', mode: 'branch', node_id: '2', parent_id: '0', interventions: [{ param: 'monthly_net_income', op: 'add', value: 1800, from_month: 0, to_month: 24 }], label: "Master's + 40% job" }, { nodeLabel: tr(node).label }));
}
function App() {
  return <div className="stage">
    <div className="col">
      <MakeItMine lang={lang} node={node} path={['2']} tr={tr} defaultOpen={state !== 'entry'} onConfirm={(item, fields) => console.log('confirm', item, fields)} />
    </div>
    <div className="col"><YourConditions lang={lang} hideEmpty={false} /></div>
  </div>;
}
createRoot(document.getElementById('root')).render(<App />);
const say = { proposal: "I'd get a CHF 600/month scholarship for 2 years", branch: "Instead, a master's with a 40% job for CHF 1'800/month" };
if (state === 'proposal' || state === 'branch') setTimeout(() => dispatchEvent(new CustomEvent(PROPOSAL_EVENT, { detail: mockPersonalize({ text: say[state], node_id: '2', parent_id: '0', label: tr(node).label, lang }) })), 150);
if (state === 'clarify') setTimeout(() => dispatchEvent(new CustomEvent(PROPOSAL_EVENT, { detail: { status: 'clarify', question: mockPersonalize({ text: 'I would work 40% alongside', lang }).question } })), 150);
