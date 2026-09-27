import { apiClient } from "@/lib/api/client";
import type { ApiExperienceListResponse, ExperienceListFilters } from "@/types/api";
import type { ProviderMe, ProviderUpdateInput } from "@/types/provider-api";

export function getMyProvider() {
  return apiClient.get<ProviderMe>("/api/v1/providers/me");
}

export function updateMyProvider(payload: ProviderUpdateInput) {
  return apiClient.put<ProviderMe>("/api/v1/providers/me", payload);
}

function toSearchParams(filters: ExperienceListFilters): string {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.limit != null) params.set("limit", String(filters.limit));
  if (filters.offset != null) params.set("offset", String(filters.offset));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function getMyExperiences(filters: ExperienceListFilters = {}) {
  return apiClient.get<ApiExperienceListResponse>(`/api/v1/providers/me/experiences${toSearchParams(filters)}`);
}

// -- Phase 10: Provider Intelligence --
import type { 
  ProviderInsightResponse, 
  ProviderNotificationListResponse,
  ProviderNotificationResponse
} from "@/types/provider-intelligence";

export function getProviderInsights(window: string = "30d", granularity: string = "auto") {
  const params = new URLSearchParams({ window, granularity });
  return apiClient.get<ProviderInsightResponse>(`/api/v1/provider/insights?${params.toString()}`);
}

export function getProviderNotifications(unread_only: boolean = false, limit: number = 50, offset: number = 0) {
  const params = new URLSearchParams();
  if (unread_only) params.append("unread_only", "true");
  if (limit !== 50) params.append("limit", String(limit));
  if (offset !== 0) params.append("offset", String(offset));
  
  const query = params.toString();
  return apiClient.get<ProviderNotificationListResponse>(`/api/v1/provider/notifications${query ? "?" + query : ""}`);
}

export function markNotificationRead(notificationId: string) {
  return apiClient.post<void>(`/api/v1/provider/notifications/${notificationId}/read`, {});
}
