import type {
  ApiItinerary,
  ApiItineraryItem,
  BookingStatus,
  ItineraryCustomActivity,
} from "@/types/api";

/**
 * Pure, deterministic display helpers for itinerary/booking data (Phase
 * 8) — no business logic in React components (same convention as
 * lib/feasibility/feasibilityDisplay.ts). The frontend never reorders
 * `items`; these helpers only format/derive display text from the
 * backend's own ordering.
 *
 * Hard invariant: REQUESTED and ACCEPTED booking statuses are never
 * displayed as "Confirmed" — see docs/DECISIONS.md ADR-046.
 */

const BOOKING_STATUS_LABELS: Record<BookingStatus, string> = {
  REQUESTED: "Requested",
  ACCEPTED: "Accepted",
  DECLINED: "Declined",
  CANCELLED: "Cancelled",
  EXPIRED: "Expired",
};

export function bookingStatusLabel(status: BookingStatus): string {
  return BOOKING_STATUS_LABELS[status] ?? status;
}

export type BookingStatusTone = "success" | "warning" | "danger" | "neutral";

const BOOKING_STATUS_TONES: Record<BookingStatus, BookingStatusTone> = {
  REQUESTED: "warning",
  ACCEPTED: "success",
  DECLINED: "danger",
  CANCELLED: "neutral",
  EXPIRED: "neutral",
};

export function bookingStatusTone(status: BookingStatus): BookingStatusTone {
  return BOOKING_STATUS_TONES[status] ?? "neutral";
}

/** Formats a travel gap for display — never assumes 0 minutes when the
 * backend reports the transition as unknown (null). */
export function travelGapLabel(item: ApiItineraryItem): string | null {
  if (item.travel_from_previous_minutes == null) {
    if (item.sequence_order === 1) return null; // first stop: no previous gap
    return "Travel time unknown";
  }
  const minutes = Math.round(item.travel_from_previous_minutes);
  if (minutes <= 0) return null;
  return `${minutes} min travel`;
}

export function formatItemTimeRange(item: ApiItineraryItem): string {
  const start = new Date(item.planned_start);
  const end = new Date(item.planned_end);
  const fmt = (d: Date) =>
    d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${fmt(start)}–${fmt(end)}`;
}

export function formatCustomTimeRange(activity: ItineraryCustomActivity): string {
  const fmt = (value: string) =>
    new Date(value).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${fmt(activity.planned_start)}–${fmt(activity.planned_end)}`;
}

export function formatCost(cost: number | null, currency: string): string {
  if (cost == null) return "Price unavailable";
  if (cost === 0) return "Free";
  return `${currency === "INR" ? "₹" : currency + " "}${cost}`;
}

/** Renders items in EXACTLY the order the backend returned them —
 * callers must never sort/reorder this array themselves. */
export function orderedItems(itinerary: ApiItinerary): ApiItineraryItem[] {
  return itinerary.items;
}

export type ItineraryTimelineEntry =
  | { kind: "experience"; sequence_order: number; planned_start: string; item: ApiItineraryItem }
  | { kind: "custom"; sequence_order: number; planned_start: string; activity: ItineraryCustomActivity };

/** Merge the separately persisted catalog and personal entries by their
 * backend-scheduled start time; preserve backend sequence order for ties. */
export function orderedTimelineEntries(itinerary: ApiItinerary): ItineraryTimelineEntry[] {
  const entries: ItineraryTimelineEntry[] = [
    ...itinerary.items.map((item) => ({
      kind: "experience" as const,
      sequence_order: item.sequence_order,
      planned_start: item.planned_start,
      item,
    })),
    ...(itinerary.custom_activities ?? []).map((activity) => ({
      kind: "custom" as const,
      sequence_order: activity.sequence_order,
      planned_start: activity.planned_start,
      activity,
    })),
  ];
  return entries.sort((left, right) => {
    const startDifference = Date.parse(left.planned_start) - Date.parse(right.planned_start);
    return Number.isFinite(startDifference) && startDifference !== 0
      ? startDifference
      : left.sequence_order - right.sequence_order;
  });
}

export function itinerarySummaryLine(itinerary: ApiItinerary): string {
  const count = itinerary.items.length;
  const parts = [`${count} stop${count === 1 ? "" : "s"}`];
  const personalCount = itinerary.custom_activities?.length ?? 0;
  if (personalCount > 0) parts.push(`${personalCount} personal ${personalCount === 1 ? "entry" : "entries"}`);
  const cost =
    itinerary.estimated_total_cost != null
      ? formatCost(itinerary.estimated_total_cost, itinerary.currency)
      : null;
  const summary = parts.join(" · ");
  return cost ? `${summary} · ${cost}` : summary;
}

const ITINERARY_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  VALIDATED: "Ready",
  BOOKING_REQUESTED: "Booking requested",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export function itineraryStatusLabel(status: string): string {
  return ITINERARY_STATUS_LABELS[status] ?? status;
}

/**
 * Picks "the current itinerary" to hydrate the Trip page with, from the
 * traveler's full GET /api/v1/itineraries list. A CANCELLED itinerary is
 * never resurrected as the active plan — the caller falls back to the
 * empty (compose-form) state instead. The backend already returns the
 * list ordered most-recent-first (itinerary_date desc, created_at desc —
 * see ItineraryRepository.list_by_traveler); this never re-sorts, only
 * selects the first non-cancelled entry, so it can never disagree with
 * the backend's own ordering rule.
 */
export function selectCurrentItinerary(itineraries: ApiItinerary[]): ApiItinerary | null {
  return itineraries.find((itinerary) => itinerary.status !== "CANCELLED") ?? null;
}
