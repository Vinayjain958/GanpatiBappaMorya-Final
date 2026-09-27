import { apiClient } from "@/lib/api/client";
import type {
  EventResponse,
  WeatherContextResponse,
  WeatherForecastEntry,
} from "@/types/api";

/** GET /api/v1/context/weather — Phase 9, read-only, authenticated.
 * Normalized data only: never a raw OpenWeather payload or API key. Use
 * `context_status` to decide whether to show a "live" badge — never show
 * one for STALE/CACHED/UNAVAILABLE data. */
export function getWeatherContext(lat: number, lng: number, signal?: AbortSignal) {
  const params = new URLSearchParams({ lat: String(lat), lng: String(lng) });
  return apiClient.get<WeatherContextResponse>(`/api/v1/context/weather?${params.toString()}`, { signal });
}

/** GET /api/v1/context/weather/forecast — normalized and bounded forecast.
 * The OpenWeather key stays on the backend; cancellation is passed to the
 * shared API client just like current weather. */
export function getWeatherForecast(
  lat: number,
  lng: number,
  maxEntries = 8,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({
    lat: String(lat),
    lng: String(lng),
    max_entries: String(maxEntries),
  });
  return apiClient.get<WeatherForecastEntry[]>(
    `/api/v1/context/weather/forecast?${params.toString()}`,
    { signal },
  );
}

/** GET /api/v1/context/events — Phase 9, read-only, authenticated.
 * Normalized data only: never a raw Ticketmaster payload or API key. An
 * empty array is a valid "0 events found" result, never an error. */
export function getEventsContext(lat: number, lng: number, radiusM = 5000, signal?: AbortSignal) {
  const params = new URLSearchParams({ lat: String(lat), lng: String(lng), radius_m: String(radiusM) });
  return apiClient.get<EventResponse[]>(`/api/v1/context/events?${params.toString()}`, { signal });
}
