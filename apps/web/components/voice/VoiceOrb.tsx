import { Loader2, Mic, MicOff, Volume2, Wrench } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { VoiceState } from "@/types/conversation";

const STATE_ICON: Partial<Record<VoiceState, typeof Mic>> = {
  LISTENING: Mic,
  SPEAKING: Volume2,
  TOOL_EXECUTING: Wrench,
  ERROR: MicOff,
};

const PULSING_STATES: VoiceState[] = ["LISTENING", "SPEAKING"];
const BUSY_STATES: VoiceState[] = [
  "CONNECTING",
  "THINKING",
  "TOOL_EXECUTING",
  "RECONNECTING",
];

/**
 * Presentational-only state indicator. It only pulses while the voice state
 * says listening or speaking; it doesn't imply audio activity otherwise.
 */
export function VoiceOrb({ state, className }: { state: VoiceState; className?: string }) {
  const Icon = STATE_ICON[state] ?? Mic;
  const isBusy = BUSY_STATES.includes(state);
  const isPulsing = PULSING_STATES.includes(state);

  return (
    <div
      className={cn(
        "relative inline-flex size-10 shrink-0 items-center justify-center rounded-2xl transition-colors",
        state === "ERROR" ? "bg-danger-soft text-danger" : "bg-accent-soft text-accent",
        className,
      )}
    >
      {isPulsing ? (
        <span
          className="absolute inset-0 animate-ping rounded-2xl bg-accent/20 motion-reduce:animate-none"
          aria-hidden="true"
        />
      ) : null}
      {isBusy ? (
        <Loader2 className="size-4.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
      ) : (
        <Icon className="size-4.5" aria-hidden="true" />
      )}
    </div>
  );
}