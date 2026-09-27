import { apiClient } from "@/lib/api/client";
import type {
  AddItineraryItemRequest,
  ApiItinerary,
  ComposeItineraryRequest,
  ComposeItineraryResult,
  ItineraryListResponse,
  ItineraryPreviewResponse,
  PreviewIdeasRequest,
  ReplanRequest,
  ReplanResponse,
} from "@/types/api";

/** POST /api/v1/itineraries/preview — schedule and validate a live draft
 * without persisting an itinerary. */
export function previewItinerary(request: ComposeItineraryRequest, signal?: AbortSignal) {
  return apiClient.post<ItineraryPreviewResponse>("/api/v1/itineraries/preview", request, { signal });
}

/** POST /api/v1/itineraries/preview-ideas — date-checks combinations from
 * the currently loaded real catalog results in one non-persisting request. */
export function previewItineraryIdeas(request: PreviewIdeasRequest, signal?: AbortSignal) {
  return apiClient.post<ItineraryPreviewResponse[]>("/api/v1/itineraries/preview-ideas", request, { signal });
}

/** POST /api/v1/itineraries/compose — Phase 8. Runs the full backend
 * pipeline (retrieval -> feasibility -> ranking -> composition ->
 * post-composition validation -> narrative) server-side; the frontend
 * never computes feasibility or ordering itself. Returns either a
 * composed+validated ApiItinerary or a CompositionValidationResponse
 * (`valid: false`) — never a partial/forced plan. traveler_id is always
 * server-derived; this request body never carries one. */
export function composeItinerary(request: ComposeItineraryRequest, signal?: AbortSignal) {
  return apiClient.post<ComposeItineraryResult>("/api/v1/itineraries/compose", request, { signal });
}

/** GET /api/v1/itineraries — the current traveler's own itineraries only. */
export function listMyItineraries(signal?: AbortSignal) {
  return apiClient.get<ItineraryListResponse>("/api/v1/itineraries", { signal });
}

/** GET /api/v1/itineraries/{id} — 404s for an itinerary the current
 * traveler does not own (never discloses existence otherwise). */
export function getItinerary(itineraryId: string, signal?: AbortSignal) {
  return apiClient.get<ApiItinerary>(`/api/v1/itineraries/${itineraryId}`, { signal });
}

/** POST /api/v1/itineraries/{id}/items — adds one experience to an
 * existing itinerary; the backend re-validates the full resulting
 * schedule before persisting. Returns a CompositionValidationResponse
 * (`valid: false`) instead of the updated itinerary if the add would
 * make the schedule invalid. */
export function addItineraryItem(itineraryId: string, request: AddItineraryItemRequest, signal?: AbortSignal) {
  return apiClient.post<ComposeItineraryResult>(`/api/v1/itineraries/${itineraryId}/items`, request, { signal });
}

/** DELETE /api/v1/itineraries/{id} — cancels (soft-deletes) an itinerary
 * the current traveler owns. */
export function cancelItinerary(itineraryId: string, signal?: AbortSignal) {
  return apiClient.delete<void>(`/api/v1/itineraries/${itineraryId}`, { signal });
}

/** POST /api/v1/itineraries/{id}/replan — Phase 9 manual replan. Calls
 * the exact same backend ReplanningService as automatic/context-driven
 * replanning — the frontend never computes the replan itself, only
 * requests it and renders the structured result. Always pass the
 * itinerary's current `version` as `expected_version` for optimistic
 * concurrency (a stale version returns 409 ITINERARY_VERSION_CONFLICT). */
export function replanItinerary(itineraryId: string, request: ReplanRequest, signal?: AbortSignal) {
  return apiClient.post<ReplanResponse>(`/api/v1/itineraries/${itineraryId}/replan`, request, { signal });
}
