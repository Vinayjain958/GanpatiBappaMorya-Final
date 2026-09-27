import type { LucideIcon } from "lucide-react";
import { BarChart3 } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";

export function InsightPlaceholderChart({
  title,
  description,
  icon: Icon = BarChart3,
}: {
  title: string;
  description: string;
  icon?: LucideIcon;
}) {
  return (
    <Card className="h-full">
      <CardHeader className="space-y-1 p-5 pb-0">
        <h3 className="text-base font-semibold text-ink">{title}</h3>
        <p className="text-sm leading-5 text-ink-subtle">{description}</p>
      </CardHeader>

      <CardBody className="p-5">
        <div className="flex h-44 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-line-strong bg-surface-raised text-ink-subtle">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-accent-soft text-accent">
            <Icon className="size-5" aria-hidden="true" />
          </span>
          <p className="text-xs font-medium">Not available yet</p>
        </div>
      </CardBody>
    </Card>
  );
}