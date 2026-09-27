import { apiClient } from "@/lib/api/client";
import type { ReplanApplyResult, SimulationResult, WhatIfScenarioRequest } from "@/types/digitalTwin";

export function simulateItineraryWhatIf(
  itineraryId: string,
  request: WhatIfScenarioRequest,
  signal?: AbortSignal,
) {
  return apiClient.post<SimulationResult>(
    `/api/v1/digital-twin/itineraries/${itineraryId}/simulate`,
    request,
    { signal },
  );
}

export function applyItineraryWhatIf(simulationId: string, signal?: AbortSignal) {
  return apiClient.post<ReplanApplyResult>(
    `/api/v1/digital-twin/simulations/${simulationId}/apply`,
    undefined,
    { signal },
  );
}
