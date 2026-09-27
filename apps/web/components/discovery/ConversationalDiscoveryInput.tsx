"use client";

import { useId, useState } from "react";
import type { FormEvent } from "react";
import { ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { VoiceControlButton } from "@/components/voice/VoiceControlButton";
import { VoiceTranscriptPanel } from "@/components/voice/VoiceTranscriptPanel";
import { useTextConversation } from "@/hooks/useTextConversation";
import { useVoiceAgent } from "@/hooks/useVoiceAgent";
import type { DiscoveryState } from "@/types/discovery";

export interface ConversationalDiscoveryInputProps {
  size?: "hero" | "compact";
  suggestions?: string[];
  onSubmitQuery?: (query: string) => void;
  /** Real conversational discovery: text and voice turns can update discovery state. */
  onDiscoveryPatch?: (patch: Partial<DiscoveryState>) => void;
  className?: string;
}

const defaultSuggestions = [
  "3 hours in Fort with friends",
  "Local food under ₹1500",
  "Something cultural tonight",
  "Quiet places near me",
];

export function ConversationalDiscoveryInput({
  size = "hero",
  suggestions = defaultSuggestions,
  onSubmitQuery,
  onDiscoveryPatch,
  className,
}: ConversationalDiscoveryInputProps) {
  const [value, setValue] = useState("");
  const inputId = useId();
  const isHero = size === "hero";

  const noopPatch = () => {};
  const { sendMessage } = useTextConversation(onDiscoveryPatch ?? noopPatch);
  const voice = useVoiceAgent(onDiscoveryPatch ?? noopPatch);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;

    onSubmitQuery?.(trimmed);
    void sendMessage(trimmed);
  }

  return (
    <div className={cn("w-full", className)}>
      <form
        onSubmit={handleSubmit}
        role="search"
        className={cn(
          "flex items-center gap-2 rounded-full border border-line-strong/80 bg-surface/95 p-1.5 shadow-float backdrop-blur-md transition-all duration-300",
          "hover:-translate-y-0.5 hover:shadow-porcelain-hover focus-within:-translate-y-0.5 focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/10 focus-within:shadow-float",
          isHero && "p-2 sm:p-2.5",
        )}
      >
        <label htmlFor={inputId} className="sr-only">
          Describe what you&apos;re in the mood for
        </label>

        <input
          id={inputId}
          type="text"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="What are you in the mood for?"
          className={cn(
            "min-w-0 flex-1 bg-transparent px-4 text-ink placeholder:text-ink-subtle focus:outline-none",
            isHero ? "text-base sm:text-lg" : "text-sm",
          )}
        />

        <VoiceControlButton
          state={voice.state}
          isAvailable={voice.isAvailable}
          onStart={() => void voice.start()}
          onStop={voice.stop}
        />

        <button
          type="submit"
          disabled={!value.trim()}
          aria-label="Search experiences"
          className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink shadow-md transition-all duration-200 hover:-translate-y-0.5 hover:scale-105 hover:brightness-105 hover:shadow-lg active:translate-y-0 active:scale-95 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:translate-y-0 disabled:hover:scale-100"
        >
          <ArrowUp className="size-4.5 stroke-[2.5]" aria-hidden="true" />
        </button>
      </form>

      {voice.state !== "IDLE" ? (
        <div className="mt-3 space-y-2">
          <VoiceTranscriptPanel entries={voice.transcript} />
          {voice.errorMessage ? (
            <p className="text-xs text-danger">{voice.errorMessage}</p>
          ) : null}
        </div>
      ) : null}

      {suggestions.length ? (
        <div
          className="mt-3.5 flex flex-wrap justify-center gap-2 sm:justify-start"
          role="group"
          aria-label="Example prompts"
        >
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => {
                setValue(suggestion);
                onSubmitQuery?.(suggestion);
              }}
              className="rounded-full border border-line bg-surface/85 px-3.5 py-1.5 text-xs font-medium text-ink-muted shadow-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-pastel-mint/80 hover:bg-pastel-mint/30 hover:text-ink active:scale-95"
            >
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}