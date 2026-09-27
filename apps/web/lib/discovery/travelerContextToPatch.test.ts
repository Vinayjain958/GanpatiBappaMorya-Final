import { describe, expect, it } from "vitest";
import { searchArgsToDiscoveryPatch, travelerContextToDiscoveryPatch } from "@/lib/discovery/travelerContextToPatch";
import type { TravelerContext } from "@/types/conversation";

function context(overrides: Partial<TravelerContext> = {}): TravelerContext {
  return {
    raw_query: "cheap local food near Fort",
    interests: ["food"],
    category_slugs: [],
    location_text: null,
    budget: null,
    duration: null,
    party_size: null,
    time_context: null,
    notes: null,
    ...overrides,
  };
}

describe("travelerContextToDiscoveryPatch", () => {
  it("snaps the first recognized category slug", () => {
    const patch = travelerContextToDiscoveryPatch(context({ category_slugs: ["not-real", "food-drink"] }));
    expect(patch.category).toBe("food-drink");
  });

  it("drops an unrecognized category to null", () => {
    const patch = travelerContextToDiscoveryPatch(context({ category_slugs: ["not-a-real-category"] }));
    expect(patch.category).toBeNull();
  });

  it("passes budget/duration through, defaulting to any", () => {
    expect(travelerContextToDiscoveryPatch(context({ budget: "low" })).budget).toBe("low");
    expect(travelerContextToDiscoveryPatch(context()).budget).toBe("any");
    expect(travelerContextToDiscoveryPatch(context()).duration).toBe("any");
  });

  it("never maps location_text to lat/lng/locationLabel", () => {
    const patch = travelerContextToDiscoveryPatch(context({ location_text: "Fort, Mumbai" }));
    expect(patch).not.toHaveProperty("lat");
    expect(patch).not.toHaveProperty("lng");
    expect(patch).not.toHaveProperty("locationLabel");
  });

  it("uses raw_query as q, undefined when empty", () => {
    expect(travelerContextToDiscoveryPatch(context({ raw_query: "" })).q).toBeUndefined();
    expect(travelerContextToDiscoveryPatch(context({ raw_query: "food" })).q).toBe("food");
  });
});

describe("searchArgsToDiscoveryPatch", () => {
  it("snaps category_slug when recognized", () => {
    expect(searchArgsToDiscoveryPatch({ category_slug: "museums" }).category).toBe("museums");
  });

  it("drops an unrecognized category_slug to null", () => {
    expect(searchArgsToDiscoveryPatch({ category_slug: "bogus" }).category).toBeNull();
  });

  it("passes q through", () => {
    expect(searchArgsToDiscoveryPatch({ q: "street food" }).q).toBe("street food");
  });
});
