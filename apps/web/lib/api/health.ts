import { apiClient } from "@/lib/api/client";

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

/** Calls the FastAPI GET /api/v1/health endpoint. The only live backend call in Phase 1. */
export function getHealth(signal?: AbortSignal) {
  return apiClient.get<HealthResponse>("/api/v1/health", { signal });
}
