const base = (import.meta.env?.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

export async function apiRequest(path, { body, method = 'POST', signal } = {}) {
  const multipart = body instanceof FormData;
  const response = await fetch(`${base}${path}`, {
    method, signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(30000)]) : AbortSignal.timeout(30000),
    headers: body !== undefined && !multipart ? { 'Content-Type': 'application/json' } : undefined,
    body: body === undefined || multipart ? body : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`The API returned ${response.status}. ${response.status === 503
    ? 'This service is unavailable; try text input instead.' : 'Check the backend and try again.'}`);
  return response.json();
}
