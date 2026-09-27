import { describe, expect, it } from "vitest";
import {
  bookingStatusLabel,
  bookingStatusTone,
  formatCost,
  formatItemTimeRange,
  itinerarySummaryLine,
  itineraryStatusLabel,
  orderedItems,
  selectCurrentItinerary,
  travelGapLabel,
} from "@/lib/itinerary/itineraryDisplay";
import type { ApiItinerary, ApiItineraryItem } from "@/types/api";

function makeItem(overrides: Partial<ApiItineraryItem> = {}): ApiItineraryItem {
  return {
    id: "item-1",
    experience_id: "exp-1",
    sequence_order: 1,
    planned_start: "2026-10-12T10:00:00Z",
    planned_end: "2026-10-12T11:00:00Z",
    duration_minutes: 60,
    travel_from_previous_minutes: null,
    travel_from_previous_distance_km: null,
    travel_mode: null,
    buffer_before_minutes: 10,
    buffer_after_minutes: 0,
    estimated_cost: 200,
    source_rank_position: 1,
    source_ranking_score: 0.9,
    narrative_text: null,
    title: "Test Experience",
    short_description: "A test.",
    category_name: "Food",
    location_place_name: "Test Place",
    location_latitude: 18.9,
    location_longitude: 72.8,
    is_locked: false,
    item_state: "ACTIVE",
    ...overrides,
  };
}

function makeItinerary(items: ApiItineraryItem[], overrides: Partial<ApiItinerary> = {}): ApiItinerary {
  return {
    id: "itin-1",
    traveler_id: "trav-1",
    title: "Test Itinerary",
    itinerary_date: "2026-10-12",
    start_time: "09:00:00",
    end_time: "18:00:00",
    status: "VALIDATED",
    source: "COMPOSER",
    total_duration_minutes: 60,
    total_travel_minutes: 0,
    estimated_total_cost: 200,
    currency: "INR",
    narrative_title: null,
    narrative_summary: null,
    narrative_closing_message: null,
    ranking_model_version: "weighted-v1",
    narrative_model_version: "gemini-narrative-v1",
    generated_at: null,
    created_at: "2026-10-12T00:00:00Z",
    updated_at: "2026-10-12T00:00:00Z",
    items,
    version: 1,
    replanning_status: "STABLE",
    context_last_updated_at: null,
    ...overrides,
  };
}

describe("bookingStatusLabel / bookingStatusTone", () => {
  it("never labels REQUESTED as Confirmed", () => {
    expect(bookingStatusLabel("REQUESTED")).toBe("Requested");
    expect(bookingStatusLabel("REQUESTED")).not.toMatch(/confirmed/i);
  });

  it("never labels ACCEPTED as Confirmed", () => {
    expect(bookingStatusLabel("ACCEPTED")).toBe("Accepted");
    expect(bookingStatusLabel("ACCEPTED")).not.toMatch(/confirmed/i);
  });

  it("gives ACCEPTED a success tone and REQUESTED a warning tone", () => {
    expect(bookingStatusTone("ACCEPTED")).toBe("success");
    expect(bookingStatusTone("REQUESTED")).toBe("warning");
    expect(bookingStatusTone("DECLINED")).toBe("danger");
  });
});

describe("travelGapLabel", () => {
  it("returns null for the first item with no previous gap", () => {
    const item = makeItem({ sequence_order: 1, travel_from_previous_minutes: null });
    expect(travelGapLabel(item)).toBeNull();
  });

  it("reports unknown travel time honestly for a non-first item", () => {
    const item = makeItem({ sequence_order: 2, travel_from_previous_minutes: null });
    expect(travelGapLabel(item)).toBe("Travel time unknown");
  });

  it("formats a known travel gap", () => {
    const item = makeItem({ sequence_order: 2, travel_from_previous_minutes: 15.4 });
    expect(travelGapLabel(item)).toBe("15 min travel");
  });

  it("returns null for a zero-minute gap", () => {
    const item = makeItem({ sequence_order: 2, travel_from_previous_minutes: 0 });
    expect(travelGapLabel(item)).toBeNull();
  });
});

describe("formatCost", () => {
  it("shows Free for zero cost", () => {
    expect(formatCost(0, "INR")).toBe("Free");
  });

  it("shows Price unavailable for null", () => {
    expect(formatCost(null, "INR")).toBe("Price unavailable");
  });

  it("formats INR with the rupee symbol", () => {
    expect(formatCost(200, "INR")).toBe("₹200");
  });
});

describe("orderedItems", () => {
  it("returns items in exactly the order the backend supplied, never re-sorted", () => {
    const items = [
      makeItem({ id: "b", sequence_order: 2 }),
      makeItem({ id: "a", sequence_order: 1 }),
    ];
    const itinerary = makeItinerary(items);
    expect(orderedItems(itinerary).map((i) => i.id)).toEqual(["b", "a"]);
  });
});

describe("itinerarySummaryLine", () => {
  it("pluralizes stop count correctly", () => {
    expect(itinerarySummaryLine(makeItinerary([makeItem()]))).toMatch(/^1 stop/);
    expect(itinerarySummaryLine(makeItinerary([makeItem(), makeItem({ id: "2" })]))).toMatch(/^2 stops/);
  });
});

describe("itineraryStatusLabel", () => {
  it("never labels VALIDATED as booked/confirmed", () => {
    expect(itineraryStatusLabel("VALIDATED")).toBe("Ready");
  });

  it("labels BOOKING_REQUESTED honestly, not as confirmed", () => {
    expect(itineraryStatusLabel("BOOKING_REQUESTED")).not.toMatch(/confirmed/i);
  });
});

describe("formatItemTimeRange", () => {
  it("produces a start-end range string", () => {
    const item = makeItem({ planned_start: "2026-10-12T10:00:00Z", planned_end: "2026-10-12T11:00:00Z" });
    const result = formatItemTimeRange(item);
    expect(result).toContain("–");
  });
});

describe("selectCurrentItinerary", () => {
  it("returns null for an empty list — the caller falls back to the composer, never a fabricated plan", () => {
    expect(selectCurrentItinerary([])).toBeNull();
  });

  it("picks the first non-cancelled itinerary, trusting the backend's own ordering", () => {
    const itineraries = [
      makeItinerary([makeItem()], { id: "newest", status: "VALIDATED" }),
      makeItinerary([makeItem()], { id: "older", status: "VALIDATED" }),
    ];
    expect(selectCurrentItinerary(itineraries)?.id).toBe("newest");
  });

  it("never resurrects a CANCELLED itinerary as the current plan", () => {
    const itineraries = [
      makeItinerary([makeItem()], { id: "cancelled-one", status: "CANCELLED" }),
      makeItinerary([makeItem()], { id: "still-active", status: "VALIDATED" }),
    ];
    expect(selectCurrentItinerary(itineraries)?.id).toBe("still-active");
  });

  it("returns null when every itinerary on record is CANCELLED", () => {
    const itineraries = [makeItinerary([makeItem()], { id: "cancelled-one", status: "CANCELLED" })];
    expect(selectCurrentItinerary(itineraries)).toBeNull();
  });
});
