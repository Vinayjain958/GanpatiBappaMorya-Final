"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ExternalLink, Navigation } from "lucide-react";
import { ItineraryComposerForm } from "@/components/trip/ItineraryComposerForm";
import { RealItineraryTimeline } from "@/components/trip/RealItineraryTimeline";
import { TripAddOnsPanel } from "@/components/trip/TripAddOnsPanel";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError } from "@/lib/api/client";
import { listMyItineraries } from "@/lib/api/itineraries";
import { buildGoogleMapsDirectionsUrlFromStops } from "@/lib/itinerary/activeTripProgress";
import { selectCurrentItinerary } from "@/lib/itinerary/itineraryDisplay";
import type { ApiItinerary, ApiItineraryItem } from "@/types/api";

type HydrationState =
  | { status: "loading" }
  | { status: "loaded-with-itinerary"; itinerary: ApiItinerary }
  | { status: "loaded-without-itinerary" }
  | { status: "error"; message: string };

/**
 * Client-side composer entry point for the trips page. Auth is already
 * enforced by the parent RequireRole wrapper — an anonymous visitor never
 * reaches this component, and RequireRole only renders children once its
 * own auth check has resolved (no fetch is ever attempted while auth is
 * still loading).
 *
 * The backend database is the source of truth for whether a traveler has
 * an existing itinerary — this component never assumes "no itinerary"
 * just because local state is empty (that was the root cause of the
 * itinerary-disappears-on-refresh bug: a bare `useState(null)` was
 * treated as "nothing exists" on every remount, even though the itinerary
 * was actually sitting in the database the whole time). On mount, it
 * fetches the traveler's saved itineraries via GET /api/v1/itineraries
 * and only falls back to the composer form once that fetch has actually
 * completed and confirmed there is nothing to show — never before, and
 * never on a fetch failure (an error is shown with a retry action, not
 * silently treated as "no trip yet"). This fetch is read-only: it never
 * triggers a compose call itself, so remounts/Strict-Mode double-effects
 * can never create a duplicate itinerary.
 */
export function TripComposerSection() {
  const [state, setState] = useState<HydrationState>({ status: "loading" });
  const [startingPoint, setStartingPoint] = useState("");

  // Fetches the traveler's saved itineraries and resolves the next state.
  // Deliberately does NOT set "loading" itself — the initial useState
  // value already covers the mount case, and the explicit retry handler
  // below sets "loading" itself before calling this, satisfying the
  // lint rule against synchronous setState calls inside an effect body.
  const fetchSavedItinerary = useCallback(async (signal?: AbortSignal): Promise<HydrationState | null> => {
    try {
      const { items } = await listMyItineraries(signal);
      const current = selectCurrentItinerary(items);
      return current
        ? { status: "loaded-with-itinerary", itinerary: current }
        : { status: "loaded-without-itinerary" };
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return null;
      return {
        status: "error",
        message: err instanceof ApiError ? err.message : "Couldn't load your trip. Please try again.",
      };
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchSavedItinerary(controller.signal).then((next) => {
      if (next) setState(next);
    });
    return () => controller.abort();
  }, [fetchSavedItinerary]);

  const retry = useCallback(() => {
    setState({ status: "loading" });
    fetchSavedItinerary().then((next) => {
      if (next) setState(next);
    });
  }, [fetchSavedItinerary]);

  const itinerary = state.status === "loaded-with-itinerary" ? state.itinerary : null;
  const mapsStops = itinerary ? [
    ...itinerary.items.map((item: ApiItineraryItem) => ({
      sequenceOrder: item.sequence_order,
      latitude: item.location_latitude,
      longitude: item.location_longitude,
      locationText: null,
      travelMode: item.travel_mode,
    })),
    ...(itinerary.custom_activities ?? [])
      .filter((activity) => activity.kind !== "note")
      .map((activity) => ({
        sequenceOrder: activity.sequence_order,
        latitude: activity.latitude,
        longitude: activity.longitude,
        locationText: activity.location_text,
        travelMode: null,
      })),
  ].sort((first, second) => first.sequenceOrder - second.sequenceOrder) : [];
  const mapsUrl = itinerary ? buildGoogleMapsDirectionsUrlFromStops(
    mapsStops.map((stop) => ({
      latitude: stop.latitude,
      longitude: stop.longitude,
      locationText: stop.locationText,
      travelMode: stop.travelMode,
    })),
    startingPoint,
  ) : null;

  if (state.status === "loading") {
    return (
      <div className="space-y-3" aria-live="polite" aria-busy="true">
        <Skeleton className="h-8 w-48 rounded-xl" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <ErrorState
        title="Couldn't load your trip"
        description={state.message}
        onRetry={retry}
      />
    );
  }

  if (state.status === "loaded-with-itinerary") {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(19rem,0.85fr)] xl:items-start">
          <RealItineraryTimeline itinerary={state.itinerary} />
          <TripAddOnsPanel
            mode="saved"
            itinerary={state.itinerary}
            onItineraryUpdated={(updated) => setState({ status: "loaded-with-itinerary", itinerary: updated })}
          />
        </div>
        <div className="flex justify-center">
          {mapsUrl ? (
            <a href={mapsUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-ink px-5 text-sm font-medium text-white transition hover:bg-ink/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
              <Navigation className="size-4" aria-hidden="true" /> Google Maps directions <ExternalLink className="size-3.5" aria-hidden="true" />
            </a>
          ) : (
            <Button type="button" disabled><Navigation className="size-4" aria-hidden="true" /> Google Maps directions unavailable</Button>
          )}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="rounded-full text-accent hover:bg-accent-soft"
          onClick={() => setState({ status: "loaded-without-itinerary" })}
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Compose another itinerary
        </Button>
      </div>
    );
  }

  return (
    <ItineraryComposerForm
      onComposed={(itinerary, origin) => {
        setStartingPoint(origin);
        setState({ status: "loaded-with-itinerary", itinerary });
      }}
    />
  );
}
