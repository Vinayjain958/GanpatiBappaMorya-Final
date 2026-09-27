import { apiClient } from "@/lib/api/client";

export interface DomainIntelligenceHealth {
  configured: boolean;
  model_id: string | null;
}

/** Safe backend diagnostic: exposes integration status and model ID only. */
export function getDomainIntelligenceHealth(signal?: AbortSignal) {
  return apiClient.get<DomainIntelligenceHealth>("/api/v1/domain-intelligence/health", { signal });
}
