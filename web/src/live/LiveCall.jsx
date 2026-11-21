// Lumi Live UI (thread 11): a realtime spoken conversation with Lumi (Gemini Live through our API proxy).
// useLumiLive() is the only thing ChatPanel uses: {available, active, start, view}. When Live is not available
// (no key on the server, budget reached, API unreachable) ChatPanel keeps its classic call link.
// Lumi's mouth: 'lumi:level' {level, speaking} and her line: 'lumi:say' {text, lang, speaking} (main.jsx, #90).
// 'lumi:live' {active} tells the rest of the app a call is open (e.g. to hold the narrator's voice).
import { useEffect, useRef, useState } from 'react';
import { liveConsent } from './consent.js';
import { createPortal } from 'react-dom';
import { createLiveSession, liveStatus } from './liveSession.js';
import './live.css';

export const LIVE_TEXT = {
  en: { title: 'Live with Lumi', connecting: 'Connecting…', listening: 'Listening: just talk', speaking: 'Lumi is speaking: talk to interrupt',
    muted: 'Microphone off', mute: 'Mute microphone', unmute: 'Unmute microphone', end: 'End', type: 'Or type here…', send: 'Send',
    privacy: 'Live mode is optional: your voice goes to Google (Gemini) while the call is open. The default chat stays private.',
    mic_denied: 'The microphone is blocked. Allow it in the browser, or type below.', mic: 'No microphone found. You can type below.',
    busy: 'Another Live call is open. Try again in a moment.', budget: 'Today’s AI budget is used up. The classic chat still works.',
    no_key: 'Live mode is not configured on this server.', unreachable: 'The API is not reachable.', error: 'The Live call stopped.',
    idle: 'Call ended after 3 minutes of silence.', max_duration: 'Call ended: Live calls are kept short.', ended: 'Call ended.',
    close: 'Close', retry: 'Call again', you: 'You', lumi: 'Lumi', tool: 'checked the engine',
    consent: 'Live mode sends your voice to Google (Gemini) while the call is open. Start?', consentYes: 'Start', consentNo: 'Not now' },
  es: { title: 'Lumi en directo', connecting: 'Conectando…', listening: 'Escuchando: habla sin más', speaking: 'Lumi habla: interrúmpela cuando quieras',
    muted: 'Micrófono apagado', mute: 'Silenciar micrófono', unmute: 'Activar micrófono', end: 'Colgar', type: 'O escribe aquí…', send: 'Enviar',
    privacy: 'El modo en directo es opcional: tu voz va a Google (Gemini) mientras dura la llamada. El chat por defecto sigue siendo privado.',
    mic_denied: 'El micrófono está bloqueado. Permítelo en el navegador o escribe abajo.', mic: 'No hay micrófono. Puedes escribir abajo.',
    busy: 'Ya hay otra llamada en directo. Prueba en un momento.', budget: 'Se ha agotado el presupuesto de IA de hoy. El chat clásico sigue funcionando.',
    no_key: 'El modo en directo no está configurado en este servidor.', unreachable: 'No se puede conectar con la API.', error: 'La llamada se ha cortado.',
    idle: 'Llamada terminada tras 3 minutos de silencio.', max_duration: 'Llamada terminada: las llamadas en directo son cortas.', ended: 'Llamada terminada.',
    close: 'Cerrar', retry: 'Volver a llamar', you: 'Tú', lumi: 'Lumi', tool: 'consultó el motor',
    consent: 'El modo Live envía tu voz a Google (Gemini) mientras dura la llamada. ¿Empezar?', consentYes: 'Empezar', consentNo: 'Ahora no' },
  fr: { title: 'Lumi en direct', connecting: 'Connexion…', listening: 'À l’écoute : parle simplement', speaking: 'Lumi parle : coupe-la quand tu veux',
    muted: 'Micro coupé', mute: 'Couper le micro', unmute: 'Activer le micro', end: 'Raccrocher', type: 'Ou écris ici…', send: 'Envoyer',
    privacy: 'Le mode direct est optionnel : ta voix est envoyée à Google (Gemini) pendant l’appel. Le chat par défaut reste privé.',
    mic_denied: 'Le micro est bloqué. Autorise-le dans le navigateur, ou écris ci-dessous.', mic: 'Aucun micro trouvé. Tu peux écrire ci-dessous.',
    busy: 'Un autre appel en direct est ouvert. Réessaie dans un instant.', budget: 'Le budget IA du jour est épuisé. Le chat classique fonctionne toujours.',
    no_key: 'Le mode direct n’est pas configuré sur ce serveur.', unreachable: 'L’API est injoignable.', error: 'L’appel s’est arrêté.',
    idle: 'Appel terminé après 3 minutes de silence.', max_duration: 'Appel terminé : les appels en direct restent courts.', ended: 'Appel terminé.',
    close: 'Fermer', retry: 'Rappeler', you: 'Toi', lumi: 'Lumi', tool: 'a consulté le moteur',
    consent: 'Le mode Live envoie ta voix à Google (Gemini) pendant l’appel. Commencer ?', consentYes: 'Commencer', consentNo: 'Pas maintenant' },
  de: { title: 'Lumi live', connecting: 'Verbinde…', listening: 'Ich höre zu: sprich einfach', speaking: 'Lumi spricht: unterbrich sie jederzeit',
    muted: 'Mikrofon aus', mute: 'Mikrofon stumm', unmute: 'Mikrofon an', end: 'Auflegen', type: 'Oder hier tippen…', send: 'Senden',
    privacy: 'Der Live-Modus ist optional: Deine Stimme geht während des Anrufs an Google (Gemini). Der Standard-Chat bleibt privat.',
    mic_denied: 'Das Mikrofon ist blockiert. Erlaube es im Browser oder tippe unten.', mic: 'Kein Mikrofon gefunden. Du kannst unten tippen.',
    busy: 'Ein anderer Live-Anruf läuft. Versuch es gleich noch einmal.', budget: 'Das KI-Budget für heute ist aufgebraucht. Der normale Chat funktioniert weiter.',
    no_key: 'Der Live-Modus ist auf diesem Server nicht eingerichtet.', unreachable: 'Die API ist nicht erreichbar.', error: 'Der Anruf wurde beendet.',
    idle: 'Anruf nach 3 Minuten Stille beendet.', max_duration: 'Anruf beendet: Live-Anrufe bleiben kurz.', ended: 'Anruf beendet.',
    close: 'Schließen', retry: 'Erneut anrufen', you: 'Du', lumi: 'Lumi', tool: 'hat die Engine gefragt',
    consent: 'Der Live-Modus sendet deine Stimme während des Anrufs an Google (Gemini). Starten?', consentYes: 'Starten', consentNo: 'Nicht jetzt' },
};

const say = (detail) => dispatchEvent(new CustomEvent('lumi:say', { detail }));
const level = (detail) => dispatchEvent(new CustomEvent('lumi:level', { detail }));

/**
 * useLumiLive({context, lang, history, onUnlock}) -> {available, active, start, view}
 * history: ChatPanel's store (append(role, text, meta)); finished turns land there with meta.mode 'live'.
 */
export function useLumiLive({ context = {}, lang = 'en', history, onUnlock } = {}) {
  const T = LIVE_TEXT[lang] || LIVE_TEXT.en;
  const [status, setStatus] = useState(null);
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState('idle'); // connecting | live | ended | error
  const [info, setInfo] = useState(null);
  const [speaking, setSpeaking] = useState(false);
  const [micLevel, setMicLevel] = useState(0);
  const [muted, setMuted] = useState(false);
  const [lines, setLines] = useState({ user: '', model: '' });
  const [usd, setUsd] = useState(0);
  const [typed, setTyped] = useState('');
  const [micError, setMicError] = useState('');
  const session = useRef(null);
  const latest = useRef({});
  latest.current = { context, lang, history };

  useEffect(() => { liveStatus().then(setStatus); }, []);
  useEffect(() => () => session.current?.end('unmount'), []);
  // the user moves in the tree during the call: tools follow the current node
  const nodeKey = JSON.stringify([context.node_id, context.path, context.assumptions, context.weather]);
  useEffect(() => { if (phase === 'live') session.current?.sendContext(context); }, [nodeKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { dispatchEvent(new CustomEvent('lumi:live', { detail: { active: phase === 'live' || phase === 'connecting' } })); }, [phase]);

  // #103: ask once per session before any audio leaves the browser
  function start() {
    if (session.current && (phase === 'live' || phase === 'connecting')) { setOpen(true); return; }
    if (!liveConsent.given()) { setOpen(true); setInfo(null); setPhase('consent'); return; }
    connect();
  }
  function accept() { liveConsent.give(); connect(); }
  function decline() { setPhase('idle'); setOpen(false); }

  function connect() {
    onUnlock?.();
    setOpen(true); setInfo(null); setMicError(''); setLines({ user: '', model: '' }); setUsd(0); setMuted(false); setSpeaking(false);
    const { context: ctx, lang: l } = latest.current;
    const s = createLiveSession({ context: ctx, lang: l, on: {
      state: (st, i) => { setPhase(st); if (i) setInfo(i); },
      caption: (role, text) => {
        setLines((cur) => (role === 'user' ? { user: text, model: '' } : { ...cur, model: text }));
        if (role === 'model') say({ text, lang: latest.current.lang, speaking: true });
      },
      level: (lv, sp) => { setSpeaking(sp); level({ level: lv, speaking: sp }); },
      micLevel: (lv) => setMicLevel(lv),
      micError: (code) => setMicError(code),
      usage: (c) => setUsd(c || 0),
      turn: (t) => {
        const h = latest.current.history;
        const cx = latest.current.context;
        if (t.user) h?.append('user', t.typed ? t.user : `🎙 ${t.user}`);
        if (t.model) h?.append('assistant', t.interrupted ? `${t.model} …` : t.model, {
          mode: 'live', node_id: cx.node_id, latency_ms: t.first_audio_ms ?? undefined,
          sources: t.tools.map((x) => [x.name, x.args?.node_id && `node ${x.args.node_id}`, `${x.ms} ms`].filter(Boolean).join(' · ')),
        });
        say({ text: t.model, lang: latest.current.lang, speaking: false });
      },
      ended: () => { level({ level: 0, speaking: false }); setSpeaking(false); },
    } });
    session.current = s;
    s.start();
  }

  function end() { session.current?.end('user_ended'); }
  function close() { if (phase === 'live' || phase === 'connecting') end(); if (phase === 'consent') setPhase('idle'); setOpen(false); }
  function toggleMute() { const m = !muted; setMuted(m); session.current?.setMicMuted(m); }
  function sendTyped(e) {
    e.preventDefault();
    if (session.current?.sendText(typed)) { setLines({ user: typed.trim(), model: '' }); setTyped(''); }
  }

  const live = phase === 'live';
  const reason = info?.code || info?.reason;
  const message = phase === 'error' ? (T[reason] || T.error) : phase === 'ended' ? (T[reason] || T.ended) : '';
  const caption = phase === 'connecting' ? T.connecting : !live ? '' : speaking ? T.speaking : micError ? T[micError] : muted ? T.muted : T.listening;
  const ring = Math.round((speaking ? 0.35 : Math.min(1, micLevel * 1.5)) * 100) / 100;

  const view = open && typeof document !== 'undefined' ? createPortal(
    <section className={`lumi-live is-${phase} ${speaking ? 'is-speaking' : ''}`} role="dialog" aria-label={T.title} aria-live="polite">
      <header className="lumi-live-head">
        <span className="lumi-live-dot" style={{ '--ring': ring }} aria-hidden="true" />
        <strong>{T.title}</strong>
        {live && <span className="lumi-live-badge">LIVE</span>}
        <button type="button" className="lumi-live-x" onClick={close} aria-label={T.close} title={T.close}>×</button>
      </header>
      {phase === 'consent' && <div className="lumi-live-consent">
        <p>{T.consent}</p>
        <div className="lumi-live-actions">
          <button type="button" className="lumi-live-no" onClick={decline}>{T.consentNo}</button>
          <button type="button" className="lumi-live-yes" onClick={accept} autoFocus>{T.consentYes}</button>
        </div>
      </div>}
      {caption && <p className="lumi-live-state">{caption}</p>}
      {(lines.user || lines.model) && <div className="lumi-live-captions">
        {lines.user && <p className="is-user"><b>{T.you}</b> {lines.user}</p>}
        {lines.model && <p className="is-lumi"><b>{T.lumi}</b> {lines.model}</p>}
      </div>}
      {message && <p className={`lumi-live-msg ${phase === 'error' ? 'is-error' : ''}`} role={phase === 'error' ? 'alert' : 'status'}>{message}</p>}
      {live && <form className="lumi-live-type" onSubmit={sendTyped} autoComplete="off">
        <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={T.type} aria-label={T.type} maxLength={2000} />
        <button type="submit" disabled={!typed.trim()}>{T.send}</button>
      </form>}
      <div className="lumi-live-actions">
        {live && !micError && <button type="button" className={`lumi-live-mute ${muted ? 'is-on' : ''}`} aria-pressed={muted} onClick={toggleMute}>{muted ? T.unmute : T.mute}</button>}
        {(live || phase === 'connecting') && <button type="button" className="lumi-live-end" onClick={end}>{T.end}</button>}
        {(phase === 'ended' || phase === 'error') && <button type="button" className="lumi-live-retry" onClick={start}>{T.retry}</button>}
      </div>
      {phase !== 'consent' && <p className="lumi-live-privacy">{T.privacy}{usd > 0 && ` · USD ${usd.toFixed(3)}`}</p>}
    </section>, document.body) : null;

  const available = !!status?.available || status?.reason === 'busy';
  return { available, active: live || phase === 'connecting', start, view, status };
}
