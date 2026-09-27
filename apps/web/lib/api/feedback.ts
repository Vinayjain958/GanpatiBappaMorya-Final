import {
  RecordInteractionRequest,
  RecordInteractionResponse,
  AffinityProfileResponse
} from "@/types/api";
import { apiClient } from "./client";

export const feedbackApi = {
  recordInteraction: async (request: RecordInteractionRequest): Promise<RecordInteractionResponse> => {
    return apiClient.post("/api/v1/feedback/interactions", request);
  },

  getAffinities: async (): Promise<AffinityProfileResponse> => {
    return apiClient.get("/api/v1/feedback/profile/affinities");
  },

  getMetrics: async (): Promise<Record<string, unknown>> => {
    return apiClient.get("/api/v1/feedback/metrics");
  }
};

/** Persist a bookmark change in the existing traveler-interaction log. */
export function recordExperienceSave(experienceId: string, saved: boolean) {
  const eventId = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `bookmark-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return feedbackApi.recordInteraction({
    experience_id: experienceId,
    event_type: saved ? "SAVE" : "UNSAVE",
    client_event_id: eventId,
    occurred_at: new Date().toISOString(),
    source: "experience_card",
  });
}
