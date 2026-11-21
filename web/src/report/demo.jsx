// Dev-only harness for the path report: renders <PathReport> against the running API without the tree.
import React from 'react';
import { createRoot } from 'react-dom/client';
import PathReport from './PathReport.jsx';
import { translateNode } from '../scene/narration.js';

const q = new URLSearchParams(location.search);
const lang = q.get('lang') || 'en';
const theme = q.get('theme');
if (theme) document.documentElement.dataset.theme = theme;
document.documentElement.lang = lang;
if (q.get('app') === '1') import('../app.css'); // check the report under the app's own styles
if (q.get('seed') === '1') { // dev only: a condition on step 1, to see it in the stepper and the assumptions
  const { personalStore, buildItem } = await import('../personalize/index.js');
  if (!personalStore.list().length) personalStore.add(buildItem({ id: 'demo-a', mode: 'patch', node_id: '2', interventions: [{ param: 'monthly_net_income', op: 'add', value: 600, from_month: 0, to_month: 24 }], label: 'CHF 600/month scholarship', text: "I'd get a CHF 600/month scholarship" }, { nodeLabel: "Do a master's" }));
}
const path = (q.get('path') || '2,2.2,2.2.1').split(',').filter(Boolean);

createRoot(document.getElementById('root')).render(
  <PathReport lang={lang} tr={(n) => translateNode(n, lang)} path={path} assumptions={[]} lens={q.get('lens') === '1'} onClose={() => {}} />,
);
