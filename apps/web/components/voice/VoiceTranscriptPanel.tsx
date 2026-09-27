import { cn } from "@/lib/utils/cn";
import type { VoiceTranscriptEntry } from "@/types/conversation";

export function VoiceTranscriptPanel({
  entries,
  className,
}: {
  entries: VoiceTranscriptEntry[];
  className?: string;
}) {
  if (entries.length === 0) return null;

  return (
    <div
      role="log"
      aria-live="polite"
      aria-label="Voice conversation transcript"
      className={cn(
        "max-h-56 space-y-2 overflow-y-auto rounded-2xl border border-line bg-surface-raised p-3",
        className,
      )}
    >
      {entries.map((entry, index) => (
        <p
          key={index}
          className={cn(
            "whitespace-pre-wrap break-words rounded-xl px-3 py-2 text-sm",
            entry.role === "user" ? "bg-surface" : "bg-accent-soft/60",
          )}
        >
          <span
            className={cn(
              "font-semibold",
              entry.role === "user" ? "text-ink" : "text-accent",
            )}
          >
            {entry.role === "user" ? "You: " : "LocaLens: "}
          </span>
          <span className="text-ink-muted">{entry.text}</span>
        </p>
      ))}
    </div>
  );
}