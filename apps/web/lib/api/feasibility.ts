import { apiClient } from "@/lib/api/client";
import type {
  FeasibilityCheckRequest,
  FeasibilityVerdict,
  SemanticSearchRequest,
  SemanticSearchResponse,
} from "@/types/api";

/** POST /api/v1/experiences/semantic-search — Phase 6. Only FEASIBLE
 * candidates are ever returned in `items`; retrieval_mode is always
 * honestly reported by the backend. */
export function semanticSearchExperiences(request: SemanticSearchRequest, signal?: AbortSignal) {
  return apiClient.post<SemanticSearchResponse>("/api/v1/experiences/semantic-search", request, { signal });
}

/** POST /api/v1/feasibility/check — Phase 6. Deterministic only, no LLM
 * on this path. */
export function checkFeasibility(request: FeasibilityCheckRequest, signal?: AbortSignal) {
  return apiClient.post<FeasibilityVerdict>("/api/v1/feasibility/check", request, { signal });
}
