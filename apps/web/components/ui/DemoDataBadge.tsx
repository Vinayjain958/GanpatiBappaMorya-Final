import { FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/Badge";

/** Visible marker for any mock/demo content rendered in the UI. */
export function DemoDataBadge({ label = "Demo data" }: { label?: string }) {
  return (
    <Badge
      tone="highlight"
      className="rounded-full border border-highlight/15 px-3 py-1.5 text-[10px] font-semibold tracking-[0.12em]"
    >
      <FlaskConical className="size-3" aria-hidden="true" />
      {label}
    </Badge>
  );
}