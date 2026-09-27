/**
 * Real audio playback for Gemini Live's native audio output — 24kHz
 * 16-bit PCM chunks (base64), decoded and scheduled gapless via a
 * tracked nextStartTime queue on AudioBufferSourceNode. No fake TTS
 * placeholder, no "wait for the whole response then play" batching —
 * chunks play as they arrive.
 */

const OUTPUT_SAMPLE_RATE = 24000;

// Exported for unit testing (see audioPlayback.test.ts) — pure functions,
// no Web Audio dependency, so they're testable without a real browser.
export function base64ToInt16Array(base64: string): Int16Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}

export function int16ToFloat32(int16: Int16Array): Float32Array<ArrayBuffer> {
  const float32 = new Float32Array(new ArrayBuffer(int16.length * 4));
  for (let i = 0; i < int16.length; i++) {
    const sample = int16[i];
    float32[i] = sample < 0 ? sample / 0x8000 : sample / 0x7fff;
  }
  return float32;
}

export class PCMAudioPlayer {
  private context: AudioContext | null = null;
  private nextStartTime = 0;
  private activeSources: AudioBufferSourceNode[] = [];
  private _isPlaying = false;

  get isPlaying(): boolean {
    return this._isPlaying;
  }

  private ensureContext(): AudioContext {
    if (!this.context || this.context.state === "closed") {
      this.context = new AudioContext({ sampleRate: OUTPUT_SAMPLE_RATE });
      this.nextStartTime = this.context.currentTime;
    }
    return this.context;
  }

  enqueue(base64Pcm: string): void {
    const context = this.ensureContext();
    const int16 = base64ToInt16Array(base64Pcm);
    const float32 = int16ToFloat32(int16);

    const buffer = context.createBuffer(1, float32.length, OUTPUT_SAMPLE_RATE);
    buffer.copyToChannel(float32, 0);

    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);

    const startAt = Math.max(this.nextStartTime, context.currentTime);
    source.start(startAt);
    this.nextStartTime = startAt + buffer.duration;

    this._isPlaying = true;
    this.activeSources.push(source);
    source.onended = () => {
      this.activeSources = this.activeSources.filter((s) => s !== source);
      if (this.activeSources.length === 0) this._isPlaying = false;
    };
  }

  /** Hard-clears the queue — used for barge-in/interruption: stale
   * assistant audio must never keep playing after the user starts
   * speaking again. */
  stop(): void {
    for (const source of this.activeSources) {
      try {
        source.onended = null;
        source.stop();
      } catch {
        // Already stopped/ended — safe to ignore.
      }
    }
    this.activeSources = [];
    this._isPlaying = false;
    if (this.context) {
      this.nextStartTime = this.context.currentTime;
    }
  }

  close(): void {
    this.stop();
    if (this.context && this.context.state !== "closed") {
      void this.context.close();
    }
    this.context = null;
  }
}
