export type SocialSignalTopic =
  | "weather"
  | "flooding"
  | "road_disruption"
  | "crowding"
  | "event_disruption"
  | "heat"
  | "wind";

export interface SocialSignalCluster {
  id: string;
  topic: SocialSignalTopic;
  location_name: string;
  location_precision: "area";
  latitude: number;
  longitude: number;
  signal_count: number;
  independent_source_count: number;
  confidence: number;
  severity: "low" | "moderate" | "high";
  trend: "rising" | "steady" | "falling" | "insufficient_data";
  newest_signal_at: string;
  source_platforms: "bluesky"[];
  confidence_note: string;
}

export interface SocialSignalsResponse {
  status: "AVAILABLE" | "NO_SIGNALS" | "UNAVAILABLE" | "RATE_LIMITED" | "STALE";
  queried_location: string | null;
  location_source?: "reverse_geocoder" | "catalog_record" | "unavailable";
  radius_km: number;
  generated_at: string;
  clusters: SocialSignalCluster[];
  message: string;
}
