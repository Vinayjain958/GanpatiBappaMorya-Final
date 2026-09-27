"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowUpRight, CalendarDays, MapPinned } from "lucide-react";
import { Card, CardBody } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import { ApiError } from "@/lib/api/client";
import { listMyItineraries } from "@/lib/api/itineraries";
import { itineraryStatusLabel, selectCurrentItinerary } from "@/lib/itinerary/itineraryDisplay";
import type { ApiItinerary } from "@/types/api";

export function MyItineraryList() {
  const [items, setItems] = useState<ApiItinerary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await listMyItineraries(signal);
      if (!signal?.aborted) {
        setItems(response.items);
        setError(null);
        setLoading(false);
      }
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      if (!signal?.aborted) {
        setError(cause instanceof ApiError ? cause.message : "Couldn't load your saved trips.");
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load, retryKey]);

  if (loading) {
    return <section aria-label="Saved trips" aria-busy="true" className="space-y-3"><Skeleton className="h-7 w-48" /><Skeleton className="h-24 rounded-2xl" /></section>;
  }
  if (error) {
    return <ErrorState title="Couldn't load saved trips" description={error} onRetry={() => { setLoading(true); setRetryKey((key) => key + 1); }} />;
  }
  const current = selectCurrentItinerary(items);
  const saved = items.filter((itinerary) => itinerary.id !== current?.id);
  if (!saved.length) return null;

  return (
    <section className="space-y-4" aria-labelledby="saved-trips-heading">
      <div className="space-y-1">
        <h2 id="saved-trips-heading" className="text-xl font-semibold tracking-tight text-ink">Saved trips</h2>
        <p className="text-sm text-ink-muted">Your earlier itinerary history, including plans finalized with Collab.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {saved.map((itinerary) => (
          <Link key={itinerary.id} href={`/trip/${itinerary.id}`} className="group rounded-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
            <Card className="h-full transition duration-200 group-hover:-translate-y-0.5 group-hover:shadow-md">
              <CardBody className="flex h-full items-start justify-between gap-4 p-4 sm:p-5">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2"><h3 className="truncate font-semibold text-ink">{itinerary.title}</h3><Badge tone={itinerary.status === "CANCELLED" ? "neutral" : "accent"}>{itineraryStatusLabel(itinerary.status)}</Badge></div>
                  <p className="flex items-center gap-1.5 text-sm text-ink-muted"><CalendarDays className="size-4 shrink-0" aria-hidden="true" />{itinerary.itinerary_date}</p>
                  <p className="flex items-center gap-1.5 text-xs text-ink-subtle"><MapPinned className="size-3.5 shrink-0" aria-hidden="true" />{itinerary.items.length} stop{itinerary.items.length === 1 ? "" : "s"}{itinerary.estimated_total_cost != null ? ` · ${itinerary.currency === "INR" ? "₹" : `${itinerary.currency} `}${itinerary.estimated_total_cost}` : ""}</p>
                </div>
                <ArrowUpRight className="mt-1 size-4 shrink-0 text-ink-subtle transition group-hover:text-accent" aria-hidden="true" />
              </CardBody>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
