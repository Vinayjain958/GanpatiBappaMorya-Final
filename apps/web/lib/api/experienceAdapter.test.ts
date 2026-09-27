import { describe, expect, it } from "vitest";
import { mapApiExperienceToUi } from "./experienceAdapter";
import type { ApiExperienceSummary } from "@/types/api";

function makeApiExperience(overrides: Partial<ApiExperienceSummary> = {}): ApiExperienceSummary {
  return {
    id: "exp-1",
    title: "Grand Heritage Museum",
    short_description: "A museum.",
    category: { id: "cat-1", slug: "museums", name: "Museums", icon: null },
    location: {
      id: "loc-1",
      latitude: 18.93,
      longitude: 72.83,
      place_name: "Grand Heritage Museum",
      address: null,
      locality: "Fort",
      city: "Mumbai",
      state: null,
      country: "India",
    },
    provider: {
      id: "prov-1",
      business_name: "Grand Heritage Museum",
      provider_type: null,
      verification_status: "catalog_imported",
      is_synthetic: false,
    },
    currency: "INR",
    price: null,
    minimum_price: null,
    maximum_price: null,
    price_type: "unknown",
    is_price_estimated: false,
    duration_minutes: null,
    duration_is_estimated: false,
    rating: null,
    review_count: null,
    status: "active",
    verification_status: "unverified",
    is_synthetic: false,
    is_enriched: false,
    image: null,
    distance_km: null,
    travel_time_minutes: null,
    travel_time_source: null,
    ...overrides,
  };
}

describe("mapApiExperienceToUi — image resolution", () => {
  it("uses the resolved Wikimedia image when present", () => {
    const api = makeApiExperience({
      image: {
        url: "https://upload.wikimedia.org/wikipedia/commons/example.jpg",
        thumbnail_url: "https://thumb.wikimedia.org/example_thumb.jpg",
        source: "wikimedia_commons",
        source_url: "https://commons.wikimedia.org/wiki/File:Example.jpg",
        license: "CC BY-SA 4.0",
        license_url: "https://creativecommons.org/licenses/by-sa/4.0",
        author: "Jane Doe",
        attribution_text: "Photo: Wikimedia Commons · Author: Jane Doe · License: CC BY-SA 4.0",
        is_place_specific: true,
        is_synthetic: false,
        match_method: "exact_title",
      },
    });

    const ui = mapApiExperienceToUi(api, null);

    expect(ui.imageUrl).toBe("https://upload.wikimedia.org/wikipedia/commons/example.jpg");
    expect(ui.image.isFallback).toBe(false);
    expect(ui.image.isPlaceSpecific).toBe(true);
    expect(ui.image.author).toBe("Jane Doe");
    expect(ui.image.license).toBe("CC BY-SA 4.0");
    expect(ui.image.attributionText).toContain("Jane Doe");
  });

  it("falls back to category art when no image was resolved, never fabricating a photo", () => {
    const api = makeApiExperience({ image: null, category: { id: "cat-2", slug: "museums", name: "Museums", icon: null } });

    const ui = mapApiExperienceToUi(api, null);

    expect(ui.image.isFallback).toBe(true);
    expect(ui.image.isPlaceSpecific).toBe(false);
    expect(ui.image.attributionText).toBeNull();
    expect(ui.imageUrl).toMatch(/^https:\/\//); // still a valid, renderable URL
  });

  it("marks a semantic-fallback Wikimedia image as not place-specific", () => {
    const api = makeApiExperience({
      image: {
        url: "https://upload.wikimedia.org/wikipedia/commons/generic-museum.jpg",
        thumbnail_url: "https://thumb.wikimedia.org/generic-museum_thumb.jpg",
        source: "wikimedia_commons",
        source_url: "https://commons.wikimedia.org/wiki/File:Generic_museum.jpg",
        license: "CC0",
        license_url: null,
        author: null,
        attribution_text: "Photo: Wikimedia Commons · License: CC0",
        is_place_specific: false,
        is_synthetic: false,
        match_method: "semantic_fallback",
      },
    });

    const ui = mapApiExperienceToUi(api, null);

    expect(ui.image.isFallback).toBe(false); // it IS a real Wikimedia image
    expect(ui.image.isPlaceSpecific).toBe(false); // but not verified as this exact venue
  });

  it("never marks the category fallback image as synthetic Wikimedia content", () => {
    const api = makeApiExperience({ image: null });

    const ui = mapApiExperienceToUi(api, null);

    expect(ui.image.source).toBeNull();
  });
});

describe("mapApiExperienceToUi — reviews, ratings, hours, availability", () => {
  it("maps synthetic reviews, rating distribution, opening hours, and availability slots from detail", () => {
    const apiDetail = {
      ...makeApiExperience(),
      full_description: "Full description of museum",
      opening_hours_status: "open",
      opening_hours: [
        {
          day_of_week: 0,
          open_time: "10:00",
          close_time: "18:00",
          is_closed: false,
          is_synthetic: true,
        },
        {
          day_of_week: 1,
          open_time: null,
          close_time: null,
          is_closed: true,
          is_synthetic: true,
        },
      ],
      availability_slots: [
        {
          id: "slot-1",
          start_time: "2026-09-28T10:00:00Z",
          end_time: "2026-09-28T12:00:00Z",
          capacity: 20,
          booked_count: 5,
          is_available: true,
          is_synthetic: true,
        },
      ],
      rating_summary: {
        average_rating: 4.5,
        review_count: 2,
        rating_distribution: { "4": 1, "5": 1 },
        is_synthetic: true,
      },
      reviews: [
        {
          id: "rev-1",
          rating_value: 5,
          title: "Brilliant visit",
          body: "Really loved the historic exhibits.",
          author_display_name: "Traveler 1",
          reviewed_at: "2026-09-20T10:00:00Z",
          is_synthetic: true,
        },
      ],
      source_type: "synthetic_enrichment",
      source_name: null,
      source_license: null,
      attribution_required: false,
      attribution_text: null,
      created_at: "2026-09-26T12:00:00Z",
      updated_at: "2026-09-26T12:00:00Z",
    };

    const ui = mapApiExperienceToUi(apiDetail, null);

    expect(ui.reviews).toHaveLength(1);
    expect(ui.reviews![0]).toMatchObject({
      id: "rev-1",
      rating: 5,
      title: "Brilliant visit",
      author: "Traveler 1",
      isSynthetic: true,
    });

    expect(ui.ratingSummary).toMatchObject({
      averageRating: 4.5,
      reviewCount: 2,
      distribution: { 4: 1, 5: 1 },
      isSynthetic: true,
    });

    expect(ui.openingHoursWeekly).toHaveLength(2);
    expect(ui.openingHoursWeekly![0]).toMatchObject({
      day: "Mon",
      dayIndex: 0,
      open: "10:00",
      close: "18:00",
      isClosed: false,
      isSynthetic: true,
    });
    expect(ui.isOpeningHoursSynthetic).toBe(true);

    expect(ui.availabilitySlots).toHaveLength(1);
    expect(ui.availabilitySlots![0]).toMatchObject({
      id: "slot-1",
      capacity: 20,
      bookedCount: 5,
      isAvailable: true,
      isSynthetic: true,
    });
    expect(ui.isAvailabilitySynthetic).toBe(true);
  });
});
