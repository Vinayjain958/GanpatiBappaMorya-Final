/**
 * AudioWorkletProcessor that captures mic input and posts 16-bit
 * little-endian PCM chunks (downsampled to 16kHz mono) to the main
 * thread — the format Gemini Live's realtime audio input expects
 * (mime_type "audio/pcm;rate=16000"). Runs off the main thread so
 * capture never blocks UI rendering.
 *
 * Downsampling is a simple linear-interpolation resample from the
 * AudioContext's native sample rate (typically 48000) to 16000 — not
 * broadcast-quality, but more than sufficient for speech input, and
 * avoids pulling in a resampling library for a hackathon prototype.
 *
 * AudioWorkletGlobalScope can't import bundled modules, so this logic
 * is inlined here — it must stay in sync with the pure, unit-tested
 * copy in lib/voice/pcmResample.ts (resampleAndEncodePCM16).
 */
class PCMCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._targetSampleRate = 16000;
    this._sourceSampleRate = sampleRate; // global in AudioWorkletGlobalScope
    this._resampleRatio = this._sourceSampleRate / this._targetSampleRate;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channelData = input[0];
    if (!channelData || channelData.length === 0) return true;

    const outputLength = Math.floor(channelData.length / this._resampleRatio);
    const pcm16 = new Int16Array(outputLength);

    for (let i = 0; i < outputLength; i++) {
      const sourceIndex = i * this._resampleRatio;
      const lowerIndex = Math.floor(sourceIndex);
      const upperIndex = Math.min(lowerIndex + 1, channelData.length - 1);
      const fraction = sourceIndex - lowerIndex;
      const sample = channelData[lowerIndex] * (1 - fraction) + channelData[upperIndex] * fraction;
      const clamped = Math.max(-1, Math.min(1, sample));
      pcm16[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    }

    this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    return true;
  }
}

registerProcessor("pcm-capture-processor", PCMCaptureProcessor);
