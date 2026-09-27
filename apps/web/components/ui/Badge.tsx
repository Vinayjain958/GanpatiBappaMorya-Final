import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "highlight";

const toneClasses: Record<Tone, string> = {
  neutral: "border border-line bg-surface-sunken text-ink-muted",
  accent: "border border-transparent bg-pastel-lavender text-ink",
  success: "border border-transparent bg-success-soft text-success",
  warning: "border border-transparent bg-warning-soft text-warning",
  danger: "border border-transparent bg-danger-soft text-danger",
  highlight: "border border-transparent bg-pastel-lemon text-ink",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium leading-none",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  );
}