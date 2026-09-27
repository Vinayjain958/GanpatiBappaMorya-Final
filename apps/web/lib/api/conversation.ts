import { apiClient } from "@/lib/api/client";
import type {
  ConversationCreateResponse,
  ConversationDetailResponse,
  ConversationTurnResponse,
  LiveTokenResponse,
  SearchExperiencesArgs,
  SearchExperiencesResult,
} from "@/types/conversation";

export function createConversation(signal?: AbortSignal) {
  return apiClient.post<ConversationCreateResponse>("/api/v1/conversations", undefined, { signal });
}

export function sendConversationMessage(conversationId: string, message: string, signal?: AbortSignal) {
  return apiClient.post<ConversationTurnResponse>(
    `/api/v1/conversations/${conversationId}/messages`,
    { message },
    { signal },
  );
}

export function getConversation(conversationId: string, signal?: AbortSignal) {
  return apiClient.get<ConversationDetailResponse>(`/api/v1/conversations/${conversationId}`, { signal });
}

/**
 * Voice-path bridge: forwards a Gemini Live tool_call verbatim to the
 * backend, which is the only place search_experiences actually executes.
 * The response is forwarded back into session.sendToolResponse(...)
 * unmodified — this function contains no discovery logic of its own.
 */
export function executeToolCall(
  conversationId: string,
  name: string,
  args: SearchExperiencesArgs,
  signal?: AbortSignal,
) {
  return apiClient.post<SearchExperiencesResult>(
    `/api/v1/conversations/${conversationId}/tool-calls`,
    { name, args },
    { signal },
  );
}

/** Issues a short-lived Gemini Live ephemeral token. Traveler-only on the
 * backend. Never persist the returned token beyond in-memory use. */
export function issueLiveToken(signal?: AbortSignal) {
  return apiClient.post<LiveTokenResponse>("/api/v1/auth/live-token", undefined, { signal });
}
