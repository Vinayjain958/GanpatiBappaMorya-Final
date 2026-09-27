import { describe, expect, it } from "vitest";
import type { ApiItinerary, ApiItineraryItem, ItineraryCustomActivity } from "@/types/api";
import { buildConsecutiveRouteLegs, buildItineraryMapStops, itineraryFitBounds } from "@/lib/map/itineraryMap";

function item(
  id: string,
  sequence_order: number,
  planned_start: string,
  location_latitude: number | null,
  location_longitude: number | null,
  item_state: string = "ACTIVE",
): ApiItineraryItem {
  return {
    id,
    experience_id: `experience-${id}`,
    sequence_order,
    planned_start,
    planned_end: new Date(Date.parse(planned_start) + 30 * 60_000).toISOString(),
    duration_minutes: 30,
    travel_from_previous_minutes: null,
    travel_from_previous_distance_km: null,
    travel_mode: null,
    buffer_before_minutes: 0,
    buffer_after_minutes: 0,
    estimated_cost: 0,
    source_rank_position: null,
    source_ranking_score: null,
    narrative_text: null,
    title: id,
    short_description: null,
    category_name: "Museum",
    location_place_name: `Place ${id}`,
    location_latitude,
    location_longitude,
    is_locked: id === "locked",
    item_state,
  };
}

function custom(
  id: string,
  sequence_order: number,
  planned_start: string,
  latitude: number | null,
  longitude: number | null,
): ItineraryCustomActivity {
  return {
    id,
    sequence_order,
    title: id,
    kind: "place",
    note: null,
    location_text: `Personal place ${id}`,
    latitude,
    longitude,
    planned_start,
    planned_end: new Date(Date.parse(planned_start) + 30 * 60_000).toISOString(),
    duration_minutes: 30,
    estimated_cost: null,
  };
}

function itinerary(
  items: ApiItineraryItem[],
  custom_activities: ItineraryCustomActivity[] = [],
): ApiItinerary {
  return {
    id: "trip-1",
    traveler_id: "traveler-1",
    title: "Test trip",
    itinerary_date: "2026-09-27",
    start_time: "09:00:00",
    end_time: "15:00:00",
    status: "VALIDATED",
    source: "MANUAL",
    total_duration_minutes: null,
    total_travel_minutes: null,
    estimated_total_cost: null,
    max_budget: null,
    currency: "INR",
    narrative_title: null,
    narrative_summary: null,
    narrative_closing_message: null,
    ranking_model_version: null,
    narrative_model_version: null,
    generated_at: null,
    created_at: "2026-09-27T00:00:00Z",
    updated_at: "2026-09-27T00:00:00Z",
    items,
    custom_activities,
    version: 1,
    replanning_status: "STABLE",
    context_last_updated_at: null,
  };
}

describe("itinerary map model", () => {
  it("uses only verified coordinates and numbers stops in displayed itinerary order", () => {
    const result = buildItineraryMapStops(itinerary([
      item("unlocated", 1, "2026-09-27T09:00:00Z", null, null),
      item("one", 2, "2026-09-27T10:00:00Z", 18.93, 72.83, "AFFECTED"),
      item("two", 4, "2026-09-27T12:00:00Z", 18.94, 72.84),
    ], [custom("personal", 3, "2026-09-27T11:00:00Z", 18.935, 72.835)]));

    expect(result.map(({ id, sequence, kind, itemState }) => ({ id, sequence, kind, itemState }))).toEqual([
      { id: "one", sequence: 2, kind: "experience", itemState: "AFFECTED" },
      { id: "personal", sequence: 3, kind: "custom", itemState: "ACTIVE" },
      { id: "two", sequence: 4, kind: "experience", itemState: "ACTIVE" },
    ]);
    expect(result[0]).toMatchObject({ latitude: 18.93, longitude: 72.83, category: "Museum" });
  });

  it("does not route across an unlocated stop or infer a custom activity location", () => {
    const trip = itinerary([
      item("one", 1, "2026-09-27T09:00:00Z", 18.93, 72.83),
      item("missing", 2, "2026-09-27T10:00:00Z", 18.94, null),
      item("four", 4, "2026-09-27T12:00:00Z", 18.95, 72.85),
    ], [
      custom("no-coordinates", 3, "2026-09-27T11:00:00Z", null, null),
      custom("five", 5, "2026-09-27T13:00:00Z", 18.96, 72.86),
    ]);

    expect(buildItineraryMapStops(trip).map((stop) => stop.id)).toEqual(["one", "four", "five"]);
    expect(buildConsecutiveRouteLegs(trip)).toEqual([
      {
        fromId: "four",
        toId: "five",
        origin: { lat: 18.95, lng: 72.85 },
        destination: { lat: 18.96, lng: 72.86 },
      },
    ]);
  });

  it("includes routed geometry in fit bounds and handles a single point without over-zooming", () => {
    const geometry: GeoJSON.LineString = {
      type: "LineString",
      coordinates: [[72.7, 18.9], [72.8, 18.95]],
    };
    expect(itineraryFitBounds([{ lat: 18.93, lng: 72.83 }], [geometry])).toEqual([
      [72.7, 18.9], [72.83, 18.95],
    ]);
    expect(itineraryFitBounds([{ lat: 18.93, lng: 72.83 }])).toEqual([
      [72.825, 18.925], [72.835, 18.935],
    ]);
    expect(itineraryFitBounds([])).toBeNull();
  });
});
