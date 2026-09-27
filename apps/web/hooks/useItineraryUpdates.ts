"use client";

import { useEffect, useState } from "react";
import { connectItineraryUpdates } from "@/lib/api/itineraryUpdates";
import type { ItineraryUpdateEvent } from "@/types/api";

export type ReplanUiStatus = "idle" | "connecting" | "connected" | "replanning" | "error" | "disconnected";

export interface ItineraryUpdatesState {
  status: ReplanUiStatus;
  lastEvent: ItineraryUpdateEvent | null;
  lastUpdatedAt: Date | null;
  replanInProgress: boolean;
  requiresAction: boolean;
  lastChangeSummary: { added_items?: string[]; removed_items?: string[] } | null;
  /** Every raw event received, most recent first — capped so it never
   * grows unbounded across a long session. Purely for a "what changed"
   * history display; never used to compute anything itself. */
  recentEvents: ItineraryUpdateEvent[];
}

const MAX_RECENT_EVENTS = 20;

/**
 * Subscribes to an itinerary's live-update SSE stream
 * (GET /api/v1/itineraries/{id}/updates) and exposes its state for the
 * UI to render.
 *
 * This hook and everything downstream of it are a PURE RENDERER of
 * backend-published events. It never calculates weather impact, event
 * conflicts, travel time, ranking, or itinerary reordering itself — all
 * of that already happened server-side before an event was ever
 * published (docs/AI_CONTEXT.md hard invariant, Phase 9).
 */
export function useItineraryUpdates(itineraryId: string | null | undefined): ItineraryUpdatesState {
  const [status, setStatus] = useState<ReplanUiStatus>(itineraryId ? "connecting" : "idle");
  const [lastEvent, setLastEvent] = useState<ItineraryUpdateEvent | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [replanInProgress, setReplanInProgress] = useState(false);
  const [requiresAction, setRequiresAction] = useState(false);
  const [lastChangeSummary, setLastChangeSummary] = useState<ItineraryUpdatesState["lastChangeSummary"]>(null);
  const [recentEvents, setRecentEvents] = useState<ItineraryUpdateEvent[]>([]);

  useEffect(() => {
    if (!itineraryId) return;

    const connection = connectItineraryUpdates(itineraryId, {
      onOpen: () => setStatus("connected"),
      onError: () => setStatus("error"),
      onEvent: (event) => {
        setLastEvent(event);
        setLastUpdatedAt(new Date());
        setRecentEvents((prev) => [event, ...prev].slice(0, MAX_RECENT_EVENTS));

        switch (event.type) {
          case "connected":
            setStatus("connected");
            break;
          case "replan_started":
            setReplanInProgress(true);
            setStatus("replanning");
            break;
          case "replan_completed":
            setReplanInProgress(false);
            setRequiresAction(false);
            setStatus("connected");
            setLastChangeSummary({
              added_items: (event.data.added_items as string[]) ?? [],
              removed_items: (event.data.removed_items as string[]) ?? [],
            });
            break;
          case "replan_failed":
            setReplanInProgress(false);
            setStatus("connected");
            break;
          case "requires_action":
            setReplanInProgress(false);
            setRequiresAction(true);
            setStatus("connected");
            break;
          case "heartbeat":
          case "context_update":
          case "booking_status_update":
            break;
          default:
            break;
        }
      },
    });

    return () => {
      connection.close();
      setStatus("disconnected");
    };
  }, [itineraryId]);

  return {
    status,
    lastEvent,
    lastUpdatedAt,
    replanInProgress,
    requiresAction,
    lastChangeSummary,
    recentEvents,
  };
}
