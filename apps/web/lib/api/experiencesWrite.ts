import { apiClient } from "@/lib/api/client";
import type { ApiExperienceDetail } from "@/types/api";
import type {
  AvailabilityInput,
  AvailabilitySlot,
  AvailabilityUpdateInput,
  ExperienceCreateInput,
  ExperienceUpdateInput,
} from "@/types/provider-api";

export function createExperience(payload: ExperienceCreateInput) {
  return apiClient.post<ApiExperienceDetail>("/api/v1/experiences", payload);
}

export function updateExperience(id: string, payload: ExperienceUpdateInput) {
  return apiClient.patch<ApiExperienceDetail>(`/api/v1/experiences/${id}`, payload);
}

export function deactivateExperience(id: string) {
  return apiClient.delete<ApiExperienceDetail>(`/api/v1/experiences/${id}`);
}

export function listAvailability(experienceId: string) {
  return apiClient.get<AvailabilitySlot[]>(`/api/v1/experiences/${experienceId}/availability`);
}

export function createAvailability(experienceId: string, payload: AvailabilityInput) {
  return apiClient.post<AvailabilitySlot>(`/api/v1/experiences/${experienceId}/availability`, payload);
}

export function updateAvailability(
  experienceId: string,
  availabilityId: string,
  payload: AvailabilityUpdateInput,
) {
  return apiClient.patch<AvailabilitySlot>(
    `/api/v1/experiences/${experienceId}/availability/${availabilityId}`,
    payload,
  );
}

export function deactivateAvailability(experienceId: string, availabilityId: string) {
  return apiClient.delete<AvailabilitySlot>(
    `/api/v1/experiences/${experienceId}/availability/${availabilityId}`,
  );
}
