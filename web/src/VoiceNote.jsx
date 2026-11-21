import React, { useEffect, useRef, useState } from 'react';
import { encodeWav } from './wav.js';

// Records from the microphone and hands a WAV file to onSend as soon as recording stops
// (no extra "send" click). Stops by itself at 60 seconds. Lluc's recording logic, as a hook.
export function useVoiceNote(onSend) {
  const [recording, setRecording] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState('');
  const recorder = useRef(null);
  const stream = useRef(null);
  const timer = useRef(null);
  const alive = useRef(true);
  const send = useRef(onSend); send.current = onSend;
  useEffect(() => () => {
    alive.current = false; clearTimeout(timer.current);
    recorder.current?.state === 'recording' && recorder.current.stop();
    stream.current?.getTracks().forEach(track => track.stop());
  }, []);
  async function start() {
    setError(''); setPreparing(true);
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!alive.current) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current = media;
      const session = new MediaRecorder(media);
      recorder.current = session;
      const chunks = [];
      let failed = false;
      session.onerror = () => {
        failed = true; clearTimeout(timer.current); media.getTracks().forEach(track => track.stop());
        if (alive.current) { setRecording(false); setPreparing(false); setError('Recording failed. Please try text or upload a voice note.'); }
      };
      session.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      session.onstop = async () => {
        clearTimeout(timer.current); media.getTracks().forEach(track => track.stop());
        if (!alive.current || failed) return;
        setRecording(false); setPreparing(true);
        let audioContext;
        try {
          audioContext = new AudioContext();
          const audio = await audioContext.decodeAudioData(await new Blob(chunks, { type: session.mimeType }).arrayBuffer());
          if (alive.current) send.current(new File([encodeWav(audio)], 'voice-note.wav', { type: 'audio/wav' }));
        } catch { if (alive.current) setError('Could not prepare the recording. Try typing instead.'); }
        finally { await audioContext?.close(); if (alive.current) setPreparing(false); }
      };
      session.start(); setRecording(true);
      timer.current = setTimeout(() => { if (session.state === 'recording') session.stop(); }, 60000);
    } catch {
      stream.current?.getTracks().forEach(track => track.stop());
      if (alive.current) setError('Microphone access failed. You can type instead.');
    } finally { if (alive.current) setPreparing(false); }
  }
  const supported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && 'MediaRecorder' in window && 'AudioContext' in window;
  return { recording, preparing, error, supported, toggle: () => (recording ? recorder.current?.stop() : start()) };
}

export default function VoiceNote({ disabled, onSend }) {
  const { recording, preparing, error, supported, toggle } = useVoiceNote(onSend);
  return <div className="voice-note"><button type="button" className="back" disabled={disabled || preparing || !supported}
    aria-pressed={recording} onClick={toggle}>
    {recording ? 'Stop and send recording' : preparing ? 'Preparing voice note…' : 'Record voice note'}</button>
    <small>{recording ? 'Recording · stops and sends at 60 seconds. Microphone stays on until stopped.' : 'Up to 60 seconds. Stop sends the note to the backend speech service.'}</small>
    {error && <p role="alert" className="negative">{error}</p>}
  </div>;
}
