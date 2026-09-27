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

/** Provider-owned shop/venue photo upload — a separate step after create/
 * update rather than part of the JSON payload, since this is the only
 * multipart request in the provider write surface. Reuses the same
 * content-validation pipeline as the traveler contribution flow; sets
 * image_source="provider_upload" server-side (never accepted from the
 * client). Replaces any previously uploaded image for this experience. */
export function uploadExperienceImage(experienceId: string, image: File) {
  const form = new FormData();
  form.set("image", image);
  return apiClient.postForm<ApiExperienceDetail>(`/api/v1/experiences/${experienceId}/image`, form);
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
