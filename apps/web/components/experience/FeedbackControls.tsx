"use client";

import { useState, useCallback } from "react";
import { ThumbsUp, ThumbsDown, Bookmark } from "lucide-react";
import { feedbackApi } from "@/lib/api/feedback";
import { InteractionEventType } from "@/types/api";
import { cn } from "@/lib/utils/cn";

export interface FeedbackControlsProps {
  experienceId: string;
  initialSaved?: boolean;
  onSaveToggle?: (saved: boolean) => void;
  className?: string;
}

export function FeedbackControls({
  experienceId,
  initialSaved = false,
  onSaveToggle,
  className,
}: FeedbackControlsProps) {
  const [isSaved, setIsSaved] = useState(initialSaved);
  const [rating, setRating] = useState<number | null>(null);
  const [isVoting, setIsVoting] = useState(false);

  const recordInteraction = useCallback(
    async (eventType: InteractionEventType, value?: number) => {
      try {
        await feedbackApi.recordInteraction({
          experience_id: experienceId,
          event_type: eventType,
          rating: value,
          client_event_id: `${experienceId}-${eventType}-${Date.now()}`,
        });
      } catch (err) {
        console.error("Failed to record interaction:", err);
      }
    },
    [experienceId],
  );

  const handleSaveToggle = () => {
    const newState = !isSaved;
    setIsSaved(newState);
    onSaveToggle?.(newState);
    recordInteraction(newState ? "SAVE" : "UNSAVE");
  };

  const handleVote = async (isPositive: boolean) => {
    if (isVoting) return;
    setIsVoting(true);
    setRating(isPositive ? 5 : 1);
    await recordInteraction("RATING", isPositive ? 5 : 1);
    setIsVoting(false);
  };

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <button
        type="button"
        onClick={(event) => {
          event.preventDefault();
          handleSaveToggle();
        }}
        aria-pressed={isSaved}
        className={cn(
          "inline-flex h-10 items-center justify-center gap-2 rounded-full border px-4 text-sm font-medium transition-colors",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
          isSaved
            ? "border-accent/25 bg-accent-soft text-accent"
            : "border-line bg-surface text-ink-muted hover:bg-surface-raised hover:text-ink",
        )}
      >
        <Bookmark className={cn("size-4", isSaved && "fill-current")} aria-hidden="true" />
        {isSaved ? "Saved" : "Save"}
      </button>

      <div className="flex h-10 items-center gap-1 rounded-full border border-line bg-surface p-1">
        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            handleVote(true);
          }}
          disabled={isVoting || rating === 5}
          className={cn(
            "inline-flex size-8 items-center justify-center rounded-full transition-colors",
            "disabled:cursor-not-allowed disabled:opacity-50",
            rating === 5
              ? "bg-success-soft text-success"
              : "text-ink-subtle hover:bg-surface-raised hover:text-ink",
          )}
          aria-label="Thumbs up"
        >
          <ThumbsUp className={cn("size-4", rating === 5 && "fill-current")} aria-hidden="true" />
        </button>

        <span className="h-4 w-px bg-line" aria-hidden="true" />

        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            handleVote(false);
          }}
          disabled={isVoting || rating === 1}
          className={cn(
            "inline-flex size-8 items-center justify-center rounded-full transition-colors",
            "disabled:cursor-not-allowed disabled:opacity-50",
            rating === 1
              ? "bg-danger-soft text-danger"
              : "text-ink-subtle hover:bg-surface-raised hover:text-ink",
          )}
          aria-label="Thumbs down"
        >
          <ThumbsDown
            className={cn("size-4", rating === 1 && "fill-current")}
            aria-hidden="true"
          />
        </button>
      </div>
    </div>
  );
}