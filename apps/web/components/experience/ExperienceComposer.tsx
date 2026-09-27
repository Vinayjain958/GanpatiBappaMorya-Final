import { ArrowDown, Clock, Sparkles, Wallet } from "lucide-react";
import type { Trip } from "@/types/trip";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DemoDataBadge } from "@/components/ui/DemoDataBadge";

/**
 * Presentation shell for the future AI Experience Composer (Phase 8).
 * Renders a structured, already-composed plan using the existing trip data.
 */
export function ExperienceComposer({ trip }: { trip: Trip }) {
  return (
    <Card className="overflow-hidden rounded-3xl">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface-raised px-5 py-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-accent">
            <Sparkles className="size-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">
              Your experience
            </p>
            <p className="truncate text-sm text-ink-muted">{trip.contextSummary}</p>
          </div>
        </div>
        <DemoDataBadge />
      </div>

      <CardBody className="space-y-2 p-4 sm:p-5">
        {trip.items.map((item, index) => (
          <div key={item.id}>
            {index > 0 ? (
              <div className="flex items-center gap-2 py-2 pl-5 text-xs text-ink-subtle">
                <span className="flex size-6 items-center justify-center rounded-full bg-highlight-soft text-highlight">
                  <ArrowDown className="size-3.5" aria-hidden="true" />
                </span>
                {item.travelMinutesFromPrevious} min travel
              </div>
            ) : null}

            <div className="flex items-start justify-between gap-3 rounded-2xl border border-line bg-surface p-4">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-wide text-accent">
                  {item.time}
                </p>
                <p className="mt-1 font-semibold text-ink">{item.title}</p>
                <p className="mt-1 text-sm text-ink-muted">
                  {item.location} &middot; {item.provider}
                </p>
              </div>
              <Badge tone="neutral" className="shrink-0">
                {item.durationMinutes} min
              </Badge>
            </div>
          </div>
        ))}
      </CardBody>

      <div className="grid grid-cols-2 gap-4 border-t border-line bg-surface-raised px-5 py-4 sm:grid-cols-4 sm:px-6">
        <div>
          <p className="flex items-center gap-1.5 text-xs text-ink-subtle">
            <Clock className="size-3.5" aria-hidden="true" />
            Total time
          </p>
          <p className="mt-1 font-semibold text-ink">
            {Math.round(trip.totalTimeMinutes / 60)}h {trip.totalTimeMinutes % 60}m
          </p>
        </div>

        <div>
          <p className="text-xs text-ink-subtle">Travel time</p>
          <p className="mt-1 font-semibold text-ink">{trip.totalTravelMinutes} min</p>
        </div>

        <div>
          <p className="flex items-center gap-1.5 text-xs text-ink-subtle">
            <Wallet className="size-3.5" aria-hidden="true" />
            Estimated cost
          </p>
          <p className="mt-1 font-semibold text-ink">₹{trip.totalCostInr}</p>
        </div>

        <div>
          <p className="text-xs text-ink-subtle">Preferences matched</p>
          <p className="mt-1 font-semibold text-ink">{trip.preferencesMatched.length}</p>
        </div>
      </div>
    </Card>
  );
}