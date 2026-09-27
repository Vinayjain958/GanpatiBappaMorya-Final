import { apiClient } from "@/lib/api/client";
import type { SocialSignalsResponse } from "@/types/social";

/** Read-only, authenticated aggregate context. No post text or author data is returned. */
export function getSocialSignals(
  latitude: number,
  longitude: number,
  radiusKm = 10,
  topics?: string[],
  sinceHours = 24,
  signal?: AbortSignal,
  itineraryItemId?: string,
) {
  const params = new URLSearchParams({
    lat: String(latitude),
    lng: String(longitude),
    radius_km: String(radiusKm),
    since_hours: String(sinceHours),
  });
  if (topics?.length) params.set("topics", topics.join(","));
  if (itineraryItemId) params.set("itinerary_item_id", itineraryItemId);
  return apiClient.get<SocialSignalsResponse>(
    `/api/v1/twin/social-signals?${params.toString()}`,
    { signal },
  );
}
