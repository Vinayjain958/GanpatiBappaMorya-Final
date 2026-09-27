import { Sparkles } from "lucide-react";
import { Badge } from "./Badge";
import { cn } from "@/lib/utils/cn";

export interface PersonalizationBadgeProps {
  signals?: string[];
  className?: string;
}

export function PersonalizationBadge({
  signals = [],
  className,
}: PersonalizationBadgeProps) {
  if (!signals || signals.length === 0) return null;

  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {signals.map((signal) => (
        <Badge
          key={signal}
          tone="accent"
          className="gap-1.5 rounded-full border border-accent/15 px-2.5 py-1 text-[10px] font-medium sm:text-xs"
        >
          <Sparkles className="size-3" aria-hidden="true" />
          {signal}
        </Badge>
      ))}
    </div>
  );
}