/** Map-only shapes. Experience and itinerary API/domain types stay intact. */

export type MapAnnotationKind = "stop" | "poi" | "social";
export type MapAnnotationTone = "normal" | "selected" | "affected" | "social";

export interface MapAnnotationProperties {
  id: string;
  label: string;
  title: string;
  description: string;
  kind: MapAnnotationKind;
  tone: MapAnnotationTone;
  locked?: boolean;
  affected?: boolean;
  scenarioAffected?: boolean;
  signalCount?: number;
  confidence?: number;
  confidenceLabel?: "low" | "medium" | "high";
  severity?: "low" | "moderate" | "high";
  trend?: "rising" | "steady" | "falling" | "insufficient_data";
}

export type MapAnnotationCollection = GeoJSON.FeatureCollection<
  GeoJSON.Point,
  MapAnnotationProperties
>;

export interface MapStop {
  id: string;
  title: string;
  sequence: number;
  latitude: number;
  longitude: number;
  plannedStart: string;
  plannedEnd: string;
  category: string;
  itemState: string;
  isLocked: boolean;
  kind: "experience" | "custom";
  locationLabel: string | null;
}

export interface MapRouteLeg {
  fromId: string;
  toId: string;
  origin: { lat: number; lng: number };
  destination: { lat: number; lng: number };
}

export interface MapRouteSegment extends MapRouteLeg {
  geometry: GeoJSON.LineString | null;
  distanceKm: number;
  durationMinutes: number;
  source: "osrm" | "haversine_estimate";
}
