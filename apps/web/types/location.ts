/** Mirrors apps/api/src/schemas/location.py. */

export type RoutingProfile = "driving" | "walking" | "cycling";
export type RouteSource = "osrm" | "haversine_estimate";

export interface LocationSearchResult {
  display_name: string;
  lat: number;
  lng: number;
  city: string | null;
  locality: string | null;
  state: string | null;
  country: string | null;
  source: string;
}

export interface LocationSearchResponse {
  items: LocationSearchResult[];
}

export interface RouteResponse {
  distance_km: number;
  duration_minutes: number;
  geometry: GeoJSON.LineString | null;
  source: RouteSource;
}

export interface TravelTimeDestinationInput {
  id: string;
  lat: number;
  lng: number;
}

export interface TravelTimeMatrixEntry {
  id: string;
  distance_km: number | null;
  duration_minutes: number | null;
}

export interface TravelTimeMatrixResponse {
  source: RouteSource;
  profile: RoutingProfile;
  destinations: TravelTimeMatrixEntry[];
}

export interface NearbyPOI {
  osm_type: string;
  osm_id: number;
  name: string;
  category: string;
  lat: number;
  lng: number;
  tags: Record<string, string>;
  distance_km: number;
}

export interface NearbyPOIResponse {
  items: NearbyPOI[];
  categories_available: string[];
}

export interface Coordinate {
  lat: number;
  lng: number;
}
