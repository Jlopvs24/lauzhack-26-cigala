// One conversation for the whole session: typed questions go to /agent/ask, voice notes to
// /voice/ask (the transcript becomes the user's message). The last 10 turns travel as history.
// An answer the backend could not ground in the engine is rejected (Lluc's rule from Chat.jsx).
import { apiRequest } from './api.js';

export async function askLumi({ question, audio, context, messages = [], signal }) {
  const history = messages.slice(-10).map(({ role, content }) => ({ role, content }));
  let body = { question: question?.trim(), context: { ...context, history } };
  if (audio) {
    if (!/\.(wav|mp3)$/i.test(audio.name) || audio.size > 10 * 1024 * 1024) throw new Error('Voice notes must be WAV or MP3, up to 10 MB.');
    body = new FormData(); body.append('audio', audio); body.append('context', JSON.stringify({ ...context, history }));
    if (context.language) body.append('language', context.language);
  }
  const data = await apiRequest(audio ? '/voice/ask' : '/agent/ask', { body, signal });
  if (typeof data.answer !== 'string' || data.grounding?.grounded === false) {
    throw new Error('The answer could not be verified against the calculation engine. Please try again.');
  }
  const user = { role: 'user', content: audio ? (data.transcript || 'Voice note') : question.trim(), voice: !!audio };
  const assistant = { role: 'assistant', content: data.answer, data };
  return { user, assistant, cost: data.cost_usd };
}
