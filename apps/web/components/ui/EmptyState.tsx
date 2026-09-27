import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-3xl border border-dashed border-line-strong bg-surface-raised px-6 py-16 text-center",
        className,
      )}
    >
      <div className="flex size-14 items-center justify-center rounded-2xl bg-accent-soft text-accent">
        <Icon className="size-6" aria-hidden="true" />
      </div>

      <div className="space-y-1.5">
        <p className="text-base font-semibold text-ink">{title}</p>
        {description ? (
          <p className="max-w-sm text-sm leading-6 text-ink-muted">{description}</p>
        ) : null}
      </div>

      {action}
    </div>
  );
}