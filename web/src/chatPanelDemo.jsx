// Dev-only demo of the chat panel (#34): npm run dev, then open /chat-panel.html.
// Not part of the production build (vite builds index.html only).
import React from 'react';
import { createRoot } from 'react-dom/client';
import ChatPanel from './ChatPanel.jsx';

const log = document.getElementById('events');
for (const name of ['panel:open', 'panel:close']) {
  addEventListener(name, (e) => { log.textContent = `${name} ${JSON.stringify(e.detail)}`; });
}
const lang = new URLSearchParams(location.search).get('lang') || 'en';
const speak = (text, l) => {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = { es: 'es-ES', fr: 'fr-FR', de: 'de-DE' }[l] || 'en-GB';
  speechSynthesis.speak(u);
};
createRoot(document.getElementById('root')).render(
  <ChatPanel lang={lang} onAnswer={(text) => speak(text, lang)} replay={speak} callUrl="http://127.0.0.1:8000/call"
    context={{ path: ['2'], node_id: '2', assumptions: [], weather: [], language: lang }} />,
);
