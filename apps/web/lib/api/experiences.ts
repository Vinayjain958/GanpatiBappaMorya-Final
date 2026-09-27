import { apiClient } from "@/lib/api/client";
import type { ApiExperienceDetail, ApiExperienceListResponse, ApiExperienceSummary, ApiOverturePlaceDatasetResponse, ExperienceListFilters } from "@/types/api";

function toSearchParams(filters: ExperienceListFilters): string {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.category) params.set("category", filters.category);
  if (filters.city) params.set("city", filters.city);
  if (filters.locality) params.set("locality", filters.locality);
  if (filters.provider) params.set("provider", filters.provider);
  if (filters.min_price != null) params.set("min_price", String(filters.min_price));
  if (filters.max_price != null) params.set("max_price", String(filters.max_price));
  if (filters.min_duration_minutes != null)
    params.set("min_duration_minutes", String(filters.min_duration_minutes));
  if (filters.max_duration_minutes != null)
    params.set("max_duration_minutes", String(filters.max_duration_minutes));
  if (filters.source_type) params.set("source_type", filters.source_type);
  if (filters.is_synthetic != null) params.set("is_synthetic", String(filters.is_synthetic));
  if (filters.status) params.set("status", filters.status);
  if (filters.lat != null) params.set("lat", String(filters.lat));
  if (filters.lng != null) params.set("lng", String(filters.lng));
  if (filters.radius_km != null) params.set("radius_km", String(filters.radius_km));
  if (filters.sort) params.set("sort", filters.sort);
  if (filters.limit != null) params.set("limit", String(filters.limit));
  if (filters.offset != null) params.set("offset", String(filters.offset));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function listExperiences(filters: ExperienceListFilters = {}, signal?: AbortSignal) {
  return apiClient.get<ApiExperienceListResponse>(`/api/v1/experiences${toSearchParams(filters)}`, {
    signal,
  });
}

/** Saved experiences for the authenticated traveler. */
export function listSavedExperiences(signal?: AbortSignal, offset = 0) {
  return apiClient.get<ApiExperienceListResponse>(
    `/api/v1/experiences/saved?limit=100&offset=${offset}`,
    { signal },
  );
}

/** Public open-data snapshot with raw source provenance separated from local estimates. */
export function getOvertureSourceDataset(signal?: AbortSignal) {
  return apiClient.get<ApiOverturePlaceDatasetResponse>(
    "/api/v1/experiences/source-data/overture",
    { signal },
  );
}

/** Expanded normalized Overture catalog. It is an archived, non-live snapshot. */
export function getOvertureCatalogAddon(signal?: AbortSignal) {
  return apiClient.get<ApiOverturePlaceDatasetResponse>(
    "/api/v1/experiences/source-data/overture/catalog",
    { signal },
  );
}

/** Loads every page for area-wide itinerary suggestions. The places still
 * come from the canonical API catalog; this helper does not invent records. */
export async function listAllExperiences(
  filters: ExperienceListFilters = {},
  signal?: AbortSignal,
): Promise<ApiExperienceSummary[]> {
  const pageSize = 100;
  const firstPage = await listExperiences({ ...filters, limit: pageSize, offset: 0 }, signal);
  const offsets: number[] = [];
  for (let offset = pageSize; offset < firstPage.total; offset += pageSize) offsets.push(offset);
  const remainingPages = await Promise.all(
    offsets.map((offset) => listExperiences({ ...filters, limit: pageSize, offset }, signal)),
  );
  const unique = new Map<string, ApiExperienceSummary>();
  for (const item of [...firstPage.items, ...remainingPages.flatMap((page) => page.items)]) {
    unique.set(item.id, item);
  }
  return [...unique.values()];
}

export function getExperience(id: string, signal?: AbortSignal) {
  return apiClient.get<ApiExperienceDetail>(`/api/v1/experiences/${id}`, { signal });
}
