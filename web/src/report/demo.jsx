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
if (q.get('p3a') === '1') { // dev only: a real engine sample (core.explore, node 1) for an API that predates core #60
  const sample = { status: 'evaluated', monthly_amount: 604.83, annual_cap: 7258, has_pension_fund: true, options: [
    { option: 'keep_in_cash', final_net_worth: 125604.88, final_liquid: 125604.88, final_pillar_3a: 0, min_cash: 8736.47, tax_saved_by_3a: 0 },
    { option: 'pay_into_3a', final_net_worth: 151819.73, final_liquid: 75520.86, final_pillar_3a: 76298.87, min_cash: 8319.98, tax_saved_by_3a: 22745.09 },
    { option: 'invest', final_net_worth: 141899.8, final_liquid: 141899.8, final_pillar_3a: 0, min_cash: 8131.64, tax_saved_by_3a: 0 }],
    max_monthly_3a_keeping_goals: { status: 'full_amount_keeps_goals', value: 604.83 } };
  const real = window.fetch.bind(window);
  window.fetch = async (url, init) => {
    const r = await real(url, init);
    if (!String(url).endsWith('/tree/explore')) return r;
    const d = await r.json();
    if (d.exploration && !d.exploration.pillar_3a) d.exploration.pillar_3a = sample;
    return new Response(JSON.stringify(d), { status: r.status, headers: { 'Content-Type': 'application/json' } });
  };
}
const path = (q.get('path') || '2,2.2,2.2.1').split(',').filter(Boolean);

createRoot(document.getElementById('root')).render(
  <PathReport lang={lang} tr={(n) => translateNode(n, lang)} path={path} assumptions={[]} lens={q.get('lens') === '1'} onClose={() => {}} />,
);
