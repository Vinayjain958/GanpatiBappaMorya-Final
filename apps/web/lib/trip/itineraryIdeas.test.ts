import { describe, expect, it } from "vitest";
import { buildItineraryIdeas } from "@/lib/trip/itineraryIdeas";
import type { ApiExperienceSummary } from "@/types/api";

function experience(index: number, locality = "Fort"): ApiExperienceSummary {
  return {
    id: `experience-${index}`,
    title: `Place ${index}`,
    short_description: "Catalog description",
    category: { id: `category-${index % 3}`, slug: `category-${index % 3}`, name: `Category ${index % 3}`, icon: null },
    location: {
      id: `location-${index}`,
      latitude: 18.93 + index * 0.0002,
      longitude: 72.83 + index * 0.0002,
      place_name: `Place ${index}`,
      address: null,
      locality,
      city: "Mumbai",
      state: "MH",
      country: "India",
    },
    provider: { id: `provider-${index}`, business_name: `Provider ${index}`, provider_type: null, verification_status: "verified", is_synthetic: false },
    currency: "INR",
    price: 100 + index,
    minimum_price: null,
    maximum_price: null,
    price_type: "fixed",
    is_price_estimated: false,
    duration_minutes: 30 + index,
    duration_is_estimated: false,
    rating: null,
    review_count: null,
    status: "active",
    verification_status: "verified",
    is_synthetic: false,
    is_enriched: true,
    image: null,
    distance_km: null,
    travel_time_minutes: null,
    travel_time_source: null,
  };
}

describe("buildItineraryIdeas", () => {
  it("builds up to two distance-aware ideas for every represented locality", () => {
    const ideas = buildItineraryIdeas([
      experience(1), experience(2), experience(3), experience(4, "Colaba"),
    ]);

    expect(ideas).toHaveLength(3);
    expect(new Set(ideas.map((idea) => idea.id)).size).toBe(ideas.length);
    expect(ideas.every((idea) => idea.experienceIds.length >= 1 && idea.experienceIds.length <= 4)).toBe(true);
    expect(ideas.filter((idea) => idea.locality === "Fort")).toHaveLength(2);
    expect(ideas.filter((idea) => idea.locality === "Colaba")).toHaveLength(1);
    const fortIdea = ideas.find((idea) => idea.locality === "Fort");
    const fortIndexes = fortIdea?.experienceIds.map((id) => Number(id.split("-").pop())) ?? [];
    expect(fortIdea?.visitMinutes).toBe(fortIndexes.reduce((sum, index) => sum + 30 + index, 0));
    expect(fortIdea?.estimatedBudget).toBe(fortIndexes.reduce((sum, index) => sum + 100 + index, 0));
  });

  it("caps results, deduplicates API pages, and omits unsupported cost and duration claims", () => {
    const first = experience(1);
    const second = experience(2);
    first.price = null;
    first.minimum_price = null;
    first.maximum_price = null;
    second.duration_minutes = null;

    const ideas = buildItineraryIdeas([first, second, first], 1);
    expect(ideas).toHaveLength(1);
    expect(ideas[0].experienceIds).toHaveLength(2);
    expect(ideas[0].visitMinutes).toBeNull();
    expect(ideas[0].estimatedBudget).toBeNull();
  });

  it("keeps distant places as separate single-stop suggestions", () => {
    const near = experience(1);
    const far = experience(2);
    far.location.latitude = 19.2;
    far.location.longitude = 72.95;
    const ideas = buildItineraryIdeas([near, far]);
    expect(ideas).toHaveLength(2);
    expect(ideas.every((idea) => idea.experienceIds.length === 1)).toBe(true);
  });

  it("caps suggestions at two per locality even when the catalog has many places", () => {
    const catalogPage = Array.from({ length: 16 }, (_, index) => experience(index + 1));
    const ideas = buildItineraryIdeas(catalogPage);
    expect(ideas).toHaveLength(2);
    expect(new Set(ideas.map((idea) => idea.id)).size).toBe(2);
    const idsBelongToCatalog = ideas.every((idea) =>
      idea.experienceIds.every((id) => catalogPage.some((item) => item.id === id)),
    );
    expect(idsBelongToCatalog).toBe(true);
  });
});
