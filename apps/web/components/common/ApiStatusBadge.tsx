"use client";

import { useHealthCheck } from "@/hooks/useHealthCheck";
import { cn } from "@/lib/utils/cn";

/** Small, honest indicator of backend reachability — not a feature, a dev signal. */
export function ApiStatusBadge() {
  const { status, data } = useHealthCheck();

  const label =
    status === "success"
      ? `API connected · v${data?.version ?? ""}`
      : status === "error"
        ? "API unreachable"
        : "Checking API…";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium",
        status === "success" && "border-success/20 bg-success-soft text-success",
        status === "error" && "border-danger/20 bg-danger-soft text-danger",
        (status === "idle" || status === "loading") &&
          "border-line bg-surface-raised text-ink-subtle",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 rounded-full",
          status === "success" && "bg-success",
          status === "error" && "bg-danger",
          (status === "idle" || status === "loading") && "bg-ink-subtle",
        )}
      />
      {label}
    </span>
  );
}