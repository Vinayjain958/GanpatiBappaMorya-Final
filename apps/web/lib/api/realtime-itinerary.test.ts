import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connectItineraryUpdates } from "./itineraryUpdates";
import type { ItineraryUpdateEvent } from "@/types/api";

/** Builds a ReadableStream<Uint8Array> that emits the given raw SSE text
 * in one chunk, simulating a real fetch() response body. */
function sseStreamFromFrames(frames: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let sent = false;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (!sent) {
        controller.enqueue(encoder.encode(frames));
        sent = true;
      } else {
        controller.close();
      }
    },
  });
}

function frame(type: string, id: number, data: Record<string, unknown>): string {
  return `id: ${id}\nevent: ${type}\ndata: ${JSON.stringify(data)}\n\n`;
}

describe("connectItineraryUpdates (SSE client)", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("parses connected + replan_started + replan_completed events in order", async () => {
    const frames =
      frame("connected", 1, { itinerary_id: "itin-1" }) +
      frame("replan_started", 2, { trigger: "WEATHER_CHANGED" }) +
      frame("replan_completed", 3, { new_version: 2, added_items: ["a"], removed_items: ["b"] });

    fetchMock.mockResolvedValue(
      new Response(sseStreamFromFrames(frames), {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
    );

    const received: ItineraryUpdateEvent[] = [];
    const opened = new Promise<void>((resolve) => {
      const connection = connectItineraryUpdates("itin-1", {
        onEvent: (event) => {
          received.push(event);
          if (received.length === 3) {
            connection.close();
            resolve();
          }
        },
      });
    });

    await opened;

    expect(received.map((e) => e.type)).toEqual(["connected", "replan_started", "replan_completed"]);
    expect(received.map((e) => e.id)).toEqual([1, 2, 3]);
    expect(received[2].data.added_items).toEqual(["a"]);
    expect(received[2].data.removed_items).toEqual(["b"]);
  });

  it("sends an Authorization header when an access token is present", async () => {
    vi.doMock("@/lib/auth/tokenStore", () => ({
      getAccessToken: () => "test-access-token",
    }));

    fetchMock.mockResolvedValue(
      new Response(sseStreamFromFrames(frame("connected", 1, {})), {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
    );

    const connection = connectItineraryUpdates("itin-2", { onEvent: () => {} });
    await new Promise((resolve) => setTimeout(resolve, 10));
    connection.close();

    expect(fetchMock).toHaveBeenCalled();
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Accept).toBe("text/event-stream");

    vi.doUnmock("@/lib/auth/tokenStore");
  });

  it("calls onError and schedules a reconnect on a failed connection", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 500 }));
    fetchMock.mockResolvedValue(
      new Response(sseStreamFromFrames(frame("connected", 1, {})), {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
    );

    let errorCalled = false;
    const connection = connectItineraryUpdates("itin-3", {
      onEvent: () => {},
      onError: () => {
        errorCalled = true;
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 20));
    connection.close();

    expect(errorCalled).toBe(true);
  });

  it("close() stops further events from being delivered", async () => {
    fetchMock.mockResolvedValue(
      new Response(sseStreamFromFrames(frame("connected", 1, {})), {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
    );

    let eventCount = 0;
    const connection = connectItineraryUpdates("itin-4", {
      onEvent: () => {
        eventCount += 1;
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 10));
    connection.close();
    const countAtClose = eventCount;

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(eventCount).toBe(countAtClose); // no further events after close()
  });
});

describe("useItineraryUpdates frontend contract (no local computation)", () => {
  it("hook source never imports weather/feasibility/ranking calculation logic", async () => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const source = await fs.readFile(
      path.resolve(__dirname, "../../hooks/useItineraryUpdates.ts"),
      "utf-8",
    );
    // The frontend must be a pure renderer of backend-published SSE
    // events — it must never import a local reordering/impact
    // calculation module.
    expect(source).not.toMatch(/weather_impact|context_impact|ranking\.ts|experience_composer/);
  });
});
