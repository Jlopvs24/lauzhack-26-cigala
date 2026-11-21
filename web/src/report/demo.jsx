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
const path = (q.get('path') || '2,2.2,2.2.1').split(',').filter(Boolean);

createRoot(document.getElementById('root')).render(
  <PathReport lang={lang} tr={(n) => translateNode(n, lang)} path={path} assumptions={[]} lens={q.get('lens') === '1'} onClose={() => {}} />,
);
