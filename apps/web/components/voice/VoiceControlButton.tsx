import { Mic, MicOff, PhoneOff } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { VoiceOrb } from "@/components/voice/VoiceOrb";
import type { VoiceState } from "@/types/conversation";

export interface VoiceControlButtonProps {
  state: VoiceState;
  isAvailable: boolean;
  onStart: () => void;
  onStop: () => void;
  className?: string;
}

const ACTIVE_STATES: VoiceState[] = [
  "CONNECTING",
  "CONNECTED",
  "LISTENING",
  "THINKING",
  "SPEAKING",
  "TOOL_EXECUTING",
  "RECONNECTING",
];

export function VoiceControlButton({
  state,
  isAvailable,
  onStart,
  onStop,
  className,
}: VoiceControlButtonProps) {
  const isActive = ACTIVE_STATES.includes(state);

  if (!isAvailable) {
    return (
      <button
        type="button"
        disabled
        aria-disabled="true"
        aria-label="Voice input unavailable in this browser"
        title="Voice input isn't supported in this browser"
        className={cn(
          "inline-flex size-10 shrink-0 cursor-not-allowed items-center justify-center rounded-2xl border border-line bg-surface-raised text-ink-subtle",
          className,
        )}
      >
        <MicOff className="size-4.5" aria-hidden="true" />
      </button>
    );
  }

  if (isActive) {
    return (
      <button
        type="button"
        onClick={onStop}
        aria-label="End voice session"
        title="End voice session"
        className={cn(
          "inline-flex size-10 shrink-0 items-center justify-center rounded-2xl border border-danger/20 bg-danger-soft text-danger transition-colors hover:brightness-95",
          className,
        )}
      >
        <PhoneOff className="size-4.5" aria-hidden="true" />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onStart}
      aria-label={state === "ERROR" ? "Voice unavailable — try again" : "Start voice conversation"}
      title={state === "ERROR" ? "Voice unavailable — try again" : "Start voice conversation"}
      className={cn(
        "inline-flex size-10 shrink-0 items-center justify-center rounded-2xl border border-highlight/20 bg-highlight-soft text-highlight transition-colors hover:border-highlight/40",
        className,
      )}
    >
      {state === "ERROR" ? (
        <VoiceOrb state={state} className="size-6" />
      ) : (
        <Mic className="size-4.5" aria-hidden="true" />
      )}
    </button>
  );
}