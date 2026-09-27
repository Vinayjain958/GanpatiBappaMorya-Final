import { apiClient } from "@/lib/api/client";
import type {
  Coordinate,
  LocationSearchResponse,
  NearbyPOIResponse,
  RouteResponse,
  RoutingProfile,
  TravelTimeDestinationInput,
  TravelTimeMatrixResponse,
} from "@/types/location";

/**
 * Only ever called from an explicit user action (search submit, "use my
 * location", route request) — never on every keystroke or map move. See
 * components/discovery/LocationSearchInput.tsx and
 * docs/DECISIONS.md ADR-022.
 */
export function searchLocation(query: string, signal?: AbortSignal) {
  return apiClient.get<LocationSearchResponse>(
    `/api/v1/location/search?q=${encodeURIComponent(query)}`,
    { signal },
  );
}

export function reverseGeocode(coordinate: Coordinate, signal?: AbortSignal) {
  return apiClient.get<LocationSearchResponse>(
    `/api/v1/location/reverse?lat=${coordinate.lat}&lng=${coordinate.lng}`,
    { signal },
  );
}

export function getNearbyPois(
  coordinate: Coordinate,
  radiusM: number,
  categories: string[],
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({
    lat: String(coordinate.lat),
    lng: String(coordinate.lng),
    radius_m: String(radiusM),
    categories: categories.join(","),
  });
  return apiClient.get<NearbyPOIResponse>(`/api/v1/location/nearby-pois?${params}`, { signal });
}

export function getRoute(
  origin: Coordinate,
  destination: Coordinate,
  options: { profile?: RoutingProfile; includeGeometry?: boolean } = {},
  signal?: AbortSignal,
) {
  return apiClient.post<RouteResponse>(
    "/api/v1/location/route",
    {
      origin,
      destination,
      profile: options.profile ?? "driving",
      include_geometry: options.includeGeometry ?? true,
    },
    { signal },
  );
}

export function getTravelTimeMatrix(
  origin: Coordinate,
  destinations: TravelTimeDestinationInput[],
  profile: RoutingProfile = "driving",
  signal?: AbortSignal,
) {
  return apiClient.post<TravelTimeMatrixResponse>(
    "/api/v1/location/travel-time-matrix",
    { origin, destinations, profile },
    { signal },
  );
}
