import type { LucideIcon } from "lucide-react";
import { AlertCircle } from "lucide-react";
import { Card, CardBody } from "@/components/ui/Card";
import type { SafetyResource } from "@/types/safety";

export function SafetyResourceCard({
  icon: Icon,
  resource,
}: {
  icon: LucideIcon;
  resource: SafetyResource;
}) {
  return (
    <Card className="h-full transition-shadow hover:shadow-soft">
      <CardBody className="flex h-full items-start gap-4 p-5">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-accent">
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="truncate font-semibold text-ink">{resource.name}</p>
          {resource.address ? (
            <p className="truncate text-sm leading-6 text-ink-muted">{resource.address}</p>
          ) : null}
          {resource.phone ? (
            <p className="truncate text-sm leading-6 text-ink-muted">{resource.phone}</p>
          ) : null}

          <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
            {resource.distance_km !== undefined ? (
              <span className="font-medium text-accent">
                {resource.distance_km.toFixed(1)} km away
              </span>
            ) : null}

            {resource.is_synthetic ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-warning-soft px-2 py-0.5 text-warning">
                <AlertCircle className="size-3" aria-hidden="true" />
                Simulated Data
              </span>
            ) : null}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
