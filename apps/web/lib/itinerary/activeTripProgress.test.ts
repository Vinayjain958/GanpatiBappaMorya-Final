import { describe, expect, it } from "vitest";
import type { ApiItineraryItem } from "@/types/api";
import {
  buildGoogleMapsDirectionsUrl,
  clearActiveTripProgress,
  countStopsBeyondMapsRouteLimit,
  countStopsWithoutCoordinates,
  getNextUncompletedStop,
  completeActiveTripStop,
  readActiveTripProgress,
  startActiveTrip,
  type ActiveTripProgress,
} from "@/lib/itinerary/activeTripProgress";

function makeItem(overrides: Partial<ApiItineraryItem> & Pick<ApiItineraryItem, "id" | "sequence_order">): ApiItineraryItem {
  return {
    experience_id: `experience-${overrides.id}`,
    planned_start: "2026-09-26T09:00:00+05:30",
    planned_end: "2026-09-26T10:00:00+05:30",
    duration_minutes: 60,
    travel_from_previous_minutes: null,
    travel_from_previous_distance_km: null,
    travel_mode: null,
    buffer_before_minutes: 0,
    buffer_after_minutes: 0,
    estimated_cost: null,
    source_rank_position: null,
    source_ranking_score: null,
    narrative_text: null,
    title: overrides.id,
    short_description: null,
    category_name: null,
    location_place_name: null,
    location_latitude: null,
    location_longitude: null,
    is_locked: false,
    item_state: "ACTIVE",
    ...overrides,
  };
}

describe("active trip progress helpers", () => {
  it("stores active progress per logged-in user and completes it after the final stop", () => {
    startActiveTrip("traveler-1", "itinerary-1");
    expect(readActiveTripProgress("traveler-1")?.status).toBe("ACTIVE");
    expect(readActiveTripProgress("traveler-2")).toBeNull();
    clearActiveTripProgress("traveler-2", "itinerary-1");
    expect(readActiveTripProgress("traveler-1")?.itineraryId).toBe("itinerary-1");

    completeActiveTripStop("traveler-1", "itinerary-1", "stop-1", ["stop-1"]);
    expect(readActiveTripProgress("traveler-1")).toMatchObject({
      itineraryId: "itinerary-1",
      completedItemIds: ["stop-1"],
      status: "COMPLETED",
    });
  });

  it("selects the first uncompleted itinerary item without changing itinerary order", () => {
    const progress: ActiveTripProgress = {
      itineraryId: "trip-1",
      startedAt: "2026-09-26T00:00:00.000Z",
      completedItemIds: ["stop-1"],
      status: "ACTIVE",
    };
    const items = [makeItem({ id: "stop-2", sequence_order: 2 }), makeItem({ id: "stop-1", sequence_order: 1 })]
      .sort((left, right) => left.sequence_order - right.sequence_order);

    expect(getNextUncompletedStop(items, progress)?.id).toBe("stop-2");
    expect(getNextUncompletedStop(items, { ...progress, status: "COMPLETED" })).toBeNull();
  });

  it("builds a Google Maps route from verified coordinates in itinerary order", () => {
    const items = [
      makeItem({ id: "third", sequence_order: 3, location_latitude: 19.076, location_longitude: 72.8777, travel_mode: "walking" }),
      makeItem({ id: "first", sequence_order: 1, location_latitude: 18.9388, location_longitude: 72.8354 }),
      makeItem({ id: "second", sequence_order: 2, location_latitude: 19.0176, location_longitude: 72.8562, travel_mode: "walking" }),
    ];

    const url = new URL(buildGoogleMapsDirectionsUrl(items)!);
    expect(url.searchParams.get("origin")).toBe("18.9388,72.8354");
    expect(url.searchParams.get("waypoints")).toBe("19.0176,72.8562");
    expect(url.searchParams.get("destination")).toBe("19.076,72.8777");
    expect(url.searchParams.get("travelmode")).toBe("walking");
  });

  it("omits stops without valid coordinates and reports their count", () => {
    const items = [
      makeItem({ id: "first", sequence_order: 1, location_latitude: 19.076, location_longitude: 72.8777 }),
      makeItem({ id: "missing", sequence_order: 2 }),
    ];

    expect(countStopsWithoutCoordinates(items)).toBe(1);
    expect(new URL(buildGoogleMapsDirectionsUrl(items)!).searchParams.get("query")).toBe("19.076,72.8777");
    expect(buildGoogleMapsDirectionsUrl([makeItem({ id: "invalid", sequence_order: 1, location_latitude: 91, location_longitude: 72 })])).toBeNull();
  });

  it("keeps cross-platform Maps route segments within the mobile waypoint limit", () => {
    const items = Array.from({ length: 7 }, (_, index) => makeItem({
      id: `stop-${index + 1}`,
      sequence_order: index + 1,
      location_latitude: 18 + index,
      location_longitude: 72 + index,
      travel_mode: "driving",
    }));

    const url = new URL(buildGoogleMapsDirectionsUrl(items)!);
    expect(url.searchParams.get("origin")).toBe("18,72");
    expect(url.searchParams.get("destination")).toBe("22,76");
    expect(url.searchParams.get("waypoints")?.split("|")).toHaveLength(3);
    expect(countStopsBeyondMapsRouteLimit(items)).toBe(2);
  });
});
