/**
 * Real microphone capture for Gemini Live — getUserMedia -> AudioContext
 * -> AudioWorklet -> 16-bit PCM chunks, per the Live API's documented
 * input format (16-bit, 16kHz, little-endian). Deliberately NOT
 * MediaRecorder/webm — that isn't the Live PCM input path.
 *
 * Permission denial / unsupported browser surface as thrown errors, not
 * a silently "started" capture — the caller (useVoiceAgent) maps these
 * to the ERROR voice state rather than pretending to be listening.
 */

export class MicrophoneUnsupportedError extends Error {
  constructor() {
    super("This browser does not support microphone capture (getUserMedia/AudioWorklet unavailable).");
    this.name = "MicrophoneUnsupportedError";
  }
}

export class MicrophonePermissionDeniedError extends Error {
  constructor() {
    super("Microphone permission was denied.");
    this.name = "MicrophonePermissionDeniedError";
  }
}

export function isMicrophoneSupported(): boolean {
  if (typeof window === "undefined") return false;
  const hasGetUserMedia = Boolean(navigator.mediaDevices?.getUserMedia);
  const hasAudioContext = Boolean(window.AudioContext || (window as unknown as { webkitAudioContext?: unknown }).webkitAudioContext);
  const hasAudioWorklet = hasAudioContext && "audioWorklet" in AudioContext.prototype;
  return hasGetUserMedia && hasAudioWorklet;
}

export class PCMAudioCapture {
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private workletNode: AudioWorkletNode | null = null;

  async start(onChunk: (pcm16: ArrayBuffer) => void): Promise<void> {
    if (!isMicrophoneSupported()) {
      throw new MicrophoneUnsupportedError();
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch {
      throw new MicrophonePermissionDeniedError();
    }

    this.context = new AudioContext();
    await this.context.audioWorklet.addModule("/worklets/pcm-capture-worklet.js");

    this.sourceNode = this.context.createMediaStreamSource(this.stream);
    this.workletNode = new AudioWorkletNode(this.context, "pcm-capture-processor");
    this.workletNode.port.onmessage = (event: MessageEvent<ArrayBuffer>) => onChunk(event.data);

    this.sourceNode.connect(this.workletNode);
  }

  stop(): void {
    this.workletNode?.port.close();
    this.workletNode?.disconnect();
    this.sourceNode?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    if (this.context && this.context.state !== "closed") {
      void this.context.close();
    }
    this.workletNode = null;
    this.sourceNode = null;
    this.stream = null;
    this.context = null;
  }
}
