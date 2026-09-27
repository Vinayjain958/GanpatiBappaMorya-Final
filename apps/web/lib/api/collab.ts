import { apiClient } from "@/lib/api/client";
import { env } from "@/lib/config/env";
import { getAccessToken } from "@/lib/auth/tokenStore";
import type { ApiExperienceSummary } from "@/types/api";
import type {
  CollabDecision,
  CollabGroup,
  CollabPlan,
  CollabPreferences,
  CollabProfilePayload,
  CollabRecommendationResponse,
  CollabWishlistItem,
  PreferenceAnalysis,
} from "@/types/collab";

const groupPath = (groupId: string) => `/api/v1/collab/groups/${encodeURIComponent(groupId)}`;

export const listCollabGroups = (signal?: AbortSignal) =>
  apiClient.get<CollabGroup[]>("/api/v1/collab/groups", { signal });

export const createCollabGroup = (payload: {
  title: string;
  destination?: string | null;
  itinerary_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  origin_latitude?: number | null;
  origin_longitude?: number | null;
  travel_mode?: "driving" | "walking" | "cycling";
  objectives?: Record<string, unknown>;
}) => apiClient.post<CollabGroup>("/api/v1/collab/groups", payload);

export const joinCollabGroup = (invite_code: string) =>
  apiClient.post<CollabGroup>("/api/v1/collab/join", { invite_code });

export const getCollabGroup = (groupId: string, signal?: AbortSignal) =>
  apiClient.get<CollabGroup>(groupPath(groupId), { signal });

export const updateCollabGroup = (groupId: string, payload: { objectives?: Record<string, unknown> }) =>
  apiClient.patch<CollabGroup>(groupPath(groupId), payload);

export const removeCollabMember = (groupId: string, memberId: string) =>
  apiClient.delete<void>(`${groupPath(groupId)}/members/${encodeURIComponent(memberId)}`);

export const updateCollabPreferences = (groupId: string, payload: CollabProfilePayload) =>
  apiClient.put<{ member_id: string; soft_preferences: Partial<CollabPreferences>; hard_constraints: Partial<CollabPreferences> }>(
    `${groupPath(groupId)}/preferences`,
    payload,
  );

export const getCollabPreferenceAnalysis = (groupId: string, signal?: AbortSignal) =>
  apiClient.get<PreferenceAnalysis>(`${groupPath(groupId)}/preference-analysis`, { signal });

export const getCollabRecommendations = (
  groupId: string,
  query?: string,
  signal?: AbortSignal,
) => {
  const params = new URLSearchParams();
  if (query?.trim()) params.set("query", query.trim());
  const queryString = params.toString();
  const suffix = queryString ? `?${queryString}` : "";
  return apiClient.get<CollabRecommendationResponse>(`${groupPath(groupId)}/recommendations${suffix}`, { signal });
};

export const getCollabWishlist = (groupId: string, signal?: AbortSignal) =>
  apiClient.get<CollabWishlistItem[]>(`${groupPath(groupId)}/wishlist`, { signal });

export const addCollabWishlistItem = (groupId: string, experience_id: string) =>
  apiClient.post<CollabWishlistItem>(`${groupPath(groupId)}/wishlist`, { experience_id });

export const removeCollabWishlistItem = (groupId: string, itemId: string) =>
  apiClient.delete<void>(`${groupPath(groupId)}/wishlist/${encodeURIComponent(itemId)}`);

export const reactToCollabWishlistItem = (
  groupId: string,
  itemId: string,
  reaction: "like" | "maybe" | "dislike",
) => apiClient.put<{ item_id: string; reaction: string }>(
  `${groupPath(groupId)}/wishlist/${encodeURIComponent(itemId)}/reaction`,
  { reaction },
);

export const getCollabDecisions = (groupId: string, signal?: AbortSignal) =>
  apiClient.get<CollabDecision[]>(`${groupPath(groupId)}/decisions`, { signal });

export const createCollabDecision = (
  groupId: string,
  title: string,
  options: { label: string; experience_id?: string | null }[],
) => apiClient.post<CollabDecision>(`${groupPath(groupId)}/decisions`, { title, options });

export const voteCollabDecision = (groupId: string, decisionId: string, option_id: string) =>
  apiClient.put<{ decision_id: string; option_id: string }>(`${groupPath(groupId)}/decisions/${encodeURIComponent(decisionId)}/vote`, { option_id });

export const closeCollabDecision = (groupId: string, decisionId: string) =>
  apiClient.post<{ decision_id: string; status: string }>(`${groupPath(groupId)}/decisions/${encodeURIComponent(decisionId)}/close`);

export const getCollabPlan = (groupId: string, signal?: AbortSignal) =>
  apiClient.get<CollabPlan | null>(`${groupPath(groupId)}/itinerary`, { signal });

export const updateCollabPlan = (
  groupId: string,
  title: string,
  items: { experience_id: string; is_optional: boolean }[],
) => apiClient.put<CollabPlan>(`${groupPath(groupId)}/itinerary`, { title, items });

export const reviewCollabPlan = (
  groupId: string,
  status: "APPROVED" | "REVISION_REQUESTED",
  note?: string,
) => apiClient.put<CollabPlan>(`${groupPath(groupId)}/itinerary/approval`, { status, note });

export const finalizeCollabPlan = (groupId: string) =>
  apiClient.post<{ status: string; trip_ids: string[]; trips: { user_id: string; itinerary_id: string }[] }>(`${groupPath(groupId)}/itinerary/finalize`);

export async function subscribeToCollabEvents(
  groupId: string,
  onEvent: (eventType: string, data: unknown) => void,
  signal: AbortSignal,
  refreshSession: () => Promise<boolean>,
): Promise<void> {
  const url = `${env.apiBaseUrl}${groupPath(groupId)}/events`;
  const open = async (retryAuth: boolean): Promise<Response> => {
    const token = getAccessToken();
    const response = await fetch(url, {
      credentials: "include",
      signal,
      headers: {
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (response.status === 401 && retryAuth && (await refreshSession())) return open(false);
    return response;
  };
  const response = await open(true);
  if (!response.ok || !response.body) throw new Error(`Collab updates unavailable (${response.status})`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (!signal.aborted) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        let eventType = "message";
        let dataText = "";
        for (const line of block.split(/\r?\n/)) {
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          if (line.startsWith("data:")) dataText += line.slice(5).trim();
        }
        if (dataText) {
          try {
            onEvent(eventType, JSON.parse(dataText) as unknown);
          } catch {
            onEvent(eventType, dataText);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export type { ApiExperienceSummary };
