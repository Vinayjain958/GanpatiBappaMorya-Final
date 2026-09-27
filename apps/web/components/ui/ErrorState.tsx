import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils/cn";

export interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = "Something went wrong",
  description = "We couldn't load this content. Please try again.",
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-3xl border border-danger/20 bg-danger-soft px-6 py-16 text-center",
        className,
      )}
    >
      <div className="flex size-14 items-center justify-center rounded-2xl bg-surface text-danger shadow-sm">
        <AlertTriangle className="size-6" aria-hidden="true" />
      </div>

      <div className="space-y-1.5">
        <p className="text-base font-semibold text-ink">{title}</p>
        <p className="max-w-sm text-sm leading-6 text-ink-muted">{description}</p>
      </div>

      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry} className="rounded-full">
          Try again
        </Button>
      ) : null}
    </div>
  );
}