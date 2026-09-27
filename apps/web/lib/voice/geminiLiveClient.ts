/**
 * Gemini Live browser wrapper (@google/genai). This is the entire
 * browser-side "bridge": it streams mic audio, plays back model audio,
 * surfaces transcripts, and forwards Gemini's tool_call to the backend
 * tool-execution endpoint before relaying the real result back to
 * Gemini via sendToolResponse. It contains NO discovery/business logic
 * of its own — search_experiences only ever executes server-side (see
 * executeToolCall in lib/api/conversation.ts).
 *
 * The ephemeral token comes from POST /api/v1/auth/live-token and is
 * held only in memory here — never written to localStorage/
 * sessionStorage/cookies. GEMINI_API_KEY never reaches this file at all.
 */

import { GoogleGenAI, type LiveServerMessage, type Session } from "@google/genai";
import { executeToolCall } from "@/lib/api/conversation";
import { PCMAudioCapture } from "@/lib/voice/audioCapture";
import { PCMAudioPlayer } from "@/lib/voice/audioPlayback";
import type { VoiceState, VoiceTranscriptEntry } from "@/types/conversation";

const RECONNECT_BEFORE_GOAWAY_MS = 5000;

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

export interface GeminiLiveClientCallbacks {
  onStateChange: (state: VoiceState) => void;
  onTranscript: (entry: VoiceTranscriptEntry) => void;
  onToolResultApplied: (args: Record<string, unknown>) => void;
  onError: (message: string) => void;
}

export class GeminiLiveClient {
  private session: Session | null = null;
  private capture = new PCMAudioCapture();
  private playback = new PCMAudioPlayer();
  private resumptionHandle: string | null = null;
  private goAwayTimer: ReturnType<typeof setTimeout> | null = null;
  private conversationId: string;
  private callbacks: GeminiLiveClientCallbacks;
  private closed = false;

  constructor(conversationId: string, callbacks: GeminiLiveClientCallbacks) {
    this.conversationId = conversationId;
    this.callbacks = callbacks;
  }

  async connect(ephemeralToken: string, model: string): Promise<void> {
    this.closed = false;
    this.callbacks.onStateChange("CONNECTING");

    const ai = new GoogleGenAI({ apiKey: ephemeralToken });

    try {
      this.session = await ai.live.connect({
        model,
        config: this.resumptionHandle
          ? { sessionResumption: { handle: this.resumptionHandle } }
          : { sessionResumption: {} },
        callbacks: {
          onopen: () => this.callbacks.onStateChange("CONNECTED"),
          onmessage: (message: LiveServerMessage) => void this.handleMessage(message),
          onerror: () => {
            this.callbacks.onError("Live connection error.");
            this.callbacks.onStateChange("ERROR");
          },
          onclose: () => {
            if (!this.closed) {
              this.callbacks.onStateChange("ENDED");
            }
          },
        },
      });
    } catch {
      this.callbacks.onError("Could not connect to Gemini Live.");
      this.callbacks.onStateChange("ERROR");
      return;
    }

    try {
      await this.capture.start((chunk) => {
        this.session?.sendRealtimeInput({
          audio: { data: arrayBufferToBase64(chunk), mimeType: "audio/pcm;rate=16000" },
        });
      });
      this.callbacks.onStateChange("LISTENING");
    } catch (error) {
      this.callbacks.onError(error instanceof Error ? error.message : "Microphone unavailable.");
      this.callbacks.onStateChange("ERROR");
    }
  }

  private async handleMessage(message: LiveServerMessage): Promise<void> {
    if (message.serverContent?.interrupted) {
      // Barge-in: stop stale assistant audio immediately.
      this.playback.stop();
    }

    if (message.serverContent?.inputTranscription?.text) {
      this.callbacks.onTranscript({
        role: "user",
        text: message.serverContent.inputTranscription.text,
        final: Boolean(message.serverContent.turnComplete),
      });
    }
    if (message.serverContent?.outputTranscription?.text) {
      this.callbacks.onTranscript({
        role: "assistant",
        text: message.serverContent.outputTranscription.text,
        final: Boolean(message.serverContent.turnComplete),
      });
    }

    const audioPart = message.serverContent?.modelTurn?.parts?.find((part) => part.inlineData?.data);
    if (audioPart?.inlineData?.data) {
      this.callbacks.onStateChange("SPEAKING");
      this.playback.enqueue(audioPart.inlineData.data);
    }
    if (message.serverContent?.turnComplete && !this.playback.isPlaying) {
      this.callbacks.onStateChange("LISTENING");
    }

    if (message.toolCall?.functionCalls?.length) {
      await this.handleToolCalls(message.toolCall.functionCalls);
    }

    if (message.sessionResumptionUpdate?.resumable && message.sessionResumptionUpdate.newHandle) {
      this.resumptionHandle = message.sessionResumptionUpdate.newHandle;
    }

    if (message.goAway) {
      this.scheduleProactiveReconnect();
    }
  }

  private async handleToolCalls(
    functionCalls: NonNullable<NonNullable<LiveServerMessage["toolCall"]>["functionCalls"]>,
  ): Promise<void> {
    this.callbacks.onStateChange("TOOL_EXECUTING");

    const responses = await Promise.all(
      functionCalls.map(async (call) => {
        if (call.name !== "search_experiences") {
          return { id: call.id, name: call.name, response: { error: "Unknown tool" } };
        }
        try {
          const result = await executeToolCall(this.conversationId, call.name, call.args ?? {});
          this.callbacks.onToolResultApplied(call.args ?? {});
          return { id: call.id, name: call.name, response: { output: result } };
        } catch {
          return { id: call.id, name: call.name, response: { error: "search_experiences failed" } };
        }
      }),
    );

    this.session?.sendToolResponse({ functionResponses: responses });
    this.callbacks.onStateChange("THINKING");
  }

  private scheduleProactiveReconnect(): void {
    if (this.goAwayTimer) return;
    this.goAwayTimer = setTimeout(() => {
      this.goAwayTimer = null;
      if (this.closed) return;
      this.callbacks.onStateChange("RECONNECTING");
      this.session?.close();
      // Caller (useVoiceAgent) observes ENDED/RECONNECTING and re-invokes
      // connect() with a fresh ephemeral token + the stored resumption handle.
    }, RECONNECT_BEFORE_GOAWAY_MS);
  }

  disconnect(): void {
    this.closed = true;
    if (this.goAwayTimer) {
      clearTimeout(this.goAwayTimer);
      this.goAwayTimer = null;
    }
    this.capture.stop();
    this.playback.close();
    this.session?.close();
    this.session = null;
    this.callbacks.onStateChange("ENDED");
  }

  get hasResumptionHandle(): boolean {
    return this.resumptionHandle !== null;
  }
}
