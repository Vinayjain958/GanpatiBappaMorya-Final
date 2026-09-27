import { describe, expect, it, vi, afterEach } from "vitest";

describe("getNearbySafetyResources", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.resetModules();
  });

  it("sends real lat/lng/radius/category as query params, not fabricated defaults", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { getNearbySafetyResources } = await import("./safety");
    await getNearbySafetyResources(18.9351, 72.8355, 3, "hospital");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.pathname).toBe("/api/v1/safety/resources/nearby");
    expect(calledUrl.searchParams.get("lat")).toBe("18.9351");
    expect(calledUrl.searchParams.get("lng")).toBe("72.8355");
    expect(calledUrl.searchParams.get("radius_km")).toBe("3");
    expect(calledUrl.searchParams.get("category")).toBe("hospital");
  });

  it("omits the category param when none is given", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { getNearbySafetyResources } = await import("./safety");
    await getNearbySafetyResources(18.9351, 72.8355);

    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.searchParams.has("category")).toBe(false);
  });

  it("preserves is_synthetic, source, and distance_km from the response untouched", async () => {
    const liveResource = {
      id: "osm:node:1",
      type: "hospital",
      name: "Live Hospital",
      latitude: 18.9351,
      longitude: 72.8355,
      distance_km: 0.42,
      source: "openstreetmap",
      is_synthetic: false,
      retrieved_at: "2026-09-25T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([liveResource]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { getNearbySafetyResources } = await import("./safety");
    const results = await getNearbySafetyResources(18.9351, 72.8355);

    expect(results).toEqual([liveResource]);
    expect(results[0].is_synthetic).toBe(false);
    expect(results[0].source).toBe("openstreetmap");
  });
});
