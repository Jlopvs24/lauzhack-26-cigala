import test from 'node:test';
import assert from 'node:assert/strict';
import { encodeWav } from './wav.js';

test('voice notes become valid mono PCM WAV with clipped samples and correct byte counts', () => {
  const buffer = encodeWav({ length: 3, sampleRate: 16000, numberOfChannels: 2,
    getChannelData: () => new Float32Array([-2, 0, 2]) });
  const view = new DataView(buffer);
  assert.equal(new TextDecoder().decode(buffer.slice(0, 4)), 'RIFF');
  assert.equal(new TextDecoder().decode(buffer.slice(8, 12)), 'WAVE');
  assert.equal(buffer.byteLength, 50);
  assert.equal(view.getUint32(4, true), 42);
  assert.equal(view.getUint32(24, true), 16000);
  assert.equal(view.getUint16(22, true), 1);
  assert.equal(view.getInt16(44, true), -32768);
  assert.equal(view.getInt16(46, true), 0);
  assert.equal(view.getInt16(48, true), 32767);
});
