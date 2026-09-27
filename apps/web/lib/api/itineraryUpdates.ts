import { env } from "@/lib/config/env";
import { getAccessToken } from "@/lib/auth/tokenStore";
import type { ItineraryUpdateEvent, ItineraryUpdateEventType } from "@/types/api";

/**
 * SSE client for GET /api/v1/itineraries/{id}/updates (Phase 9).
 *
 * Uses fetch()+ReadableStream rather than the browser EventSource API
 * because EventSource cannot send a custom Authorization header — this
 * endpoint is require_traveler-gated and needs the same Bearer access
 * token every other authenticated request uses (lib/api/client.ts).
 * `credentials: "include"` still travels the HttpOnly cookie, matching
 * the rest of the app's auth model.
 *
 * This module ONLY parses and forwards backend-published events — it
 * never computes replanning, weather impact, feasibility, or reordering
 * itself (docs/AI_CONTEXT.md hard invariant: the frontend is a pure
 * renderer of backend state for Phase 9 real-time context).
 */

export interface ItineraryUpdatesConnection {
  close: () => void;
}

export interface ItineraryUpdatesHandlers {
  onEvent: (event: ItineraryUpdateEvent) => void;
  onError?: (error: unknown) => void;
  onOpen?: () => void;
}

const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 15000;

function parseSseFrame(rawFrame: string): ItineraryUpdateEvent | null {
  let eventType: ItineraryUpdateEventType | null = null;
  let id: number | null = null;
  const dataLines: string[] = [];

  for (const line of rawFrame.split("\n")) {
    if (line.startsWith("event:")) {
      eventType = line.slice("event:".length).trim() as ItineraryUpdateEventType;
    } else if (line.startsWith("id:")) {
      const parsed = Number(line.slice("id:".length).trim());
      if (!Number.isNaN(parsed)) id = parsed;
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  if (!eventType || id === null) return null;
  let data: Record<string, unknown> = {};
  try {
    data = dataLines.length ? (JSON.parse(dataLines.join("\n")) as Record<string, unknown>) : {};
  } catch {
    data = {};
  }
  return { type: eventType, id, data };
}

/** Connects to the itinerary's live-update SSE stream, calling
 * `handlers.onEvent` for every normalized event. Automatically
 * reconnects with capped exponential backoff on connection failure.
 * Returns a handle whose `close()` stops the stream and cancels any
 * pending reconnect — callers (e.g. useItineraryUpdates) must call it on
 * unmount. */
export function connectItineraryUpdates(
  itineraryId: string,
  handlers: ItineraryUpdatesHandlers,
): ItineraryUpdatesConnection {
  let closed = false;
  let abortController: AbortController | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let attempt = 0;

  async function connectOnce(): Promise<void> {
    if (closed) return;
    abortController = new AbortController();
    const token = getAccessToken();

    try {
      const response = await fetch(`${env.apiBaseUrl}/api/v1/itineraries/${itineraryId}/updates`, {
        method: "GET",
        credentials: "include",
        headers: {
          Accept: "text/event-stream",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: abortController.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`SSE connection failed with status ${response.status}`);
      }

      attempt = 0; // reset backoff on a successful connection
      handlers.onOpen?.();

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (!closed) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const frame = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const parsed = parseSseFrame(frame);
          if (parsed) handlers.onEvent(parsed);
          boundary = buffer.indexOf("\n\n");
        }
      }
    } catch (error) {
      if (closed) return;
      handlers.onError?.(error);
    }

    if (!closed) scheduleReconnect();
  }

  function scheduleReconnect(): void {
    attempt += 1;
    const delay = Math.min(RECONNECT_BASE_DELAY_MS * 2 ** (attempt - 1), RECONNECT_MAX_DELAY_MS);
    reconnectTimer = setTimeout(() => {
      void connectOnce();
    }, delay);
  }

  void connectOnce();

  return {
    close: () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      abortController?.abort();
    },
  };
}
