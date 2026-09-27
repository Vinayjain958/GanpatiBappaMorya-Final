import { apiClient } from "@/lib/api/client";

export interface ApiCategory {
  id: string;
  slug: string;
  name: string;
  icon: string | null;
  sort_order: number;
}

export function listCategories() {
  return apiClient.get<ApiCategory[]>("/api/v1/categories");
}

export function listAvailableCategories(filters: {
  city?: string | null;
  locality?: string | null;
  lat?: number | null;
  lng?: number | null;
  radius_km?: number | null;
}, signal?: AbortSignal) {
  const params = new URLSearchParams();
  if (filters.city) params.set("city", filters.city);
  if (filters.locality) params.set("locality", filters.locality);
  if (filters.lat != null) params.set("lat", String(filters.lat));
  if (filters.lng != null) params.set("lng", String(filters.lng));
  if (filters.radius_km != null) params.set("radius_km", String(filters.radius_km));
  return apiClient.get<ApiCategory[]>(`/api/v1/categories/available?${params.toString()}`, { signal });
}
