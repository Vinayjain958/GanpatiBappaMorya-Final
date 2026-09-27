import { orderedTimelineEntries } from "@/lib/itinerary/itineraryDisplay";
import type { ApiItinerary } from "@/types/api";
import type { MapRouteLeg, MapStop } from "@/types/map";

function verifiedCoordinates(
  latitude: number | null | undefined,
  longitude: number | null | undefined,
): { lat: number; lng: number } | null {
  if (latitude == null
    || longitude == null
    || !Number.isFinite(latitude)
    || !Number.isFinite(longitude)
    || latitude < -90
    || latitude > 90
    || longitude < -180
    || longitude > 180
  ) return null;
  return { lat: latitude, lng: longitude };
}

/** Use only coordinates already returned by the itinerary API. */
export function buildItineraryMapStops(itinerary: ApiItinerary): MapStop[] {
  return orderedTimelineEntries(itinerary).flatMap((entry) => {
    const isExperience = entry.kind === "experience";
    const location = verifiedCoordinates(
      isExperience ? entry.item.location_latitude : entry.activity.latitude,
      isExperience ? entry.item.location_longitude : entry.activity.longitude,
    );
    if (!location) return [];

    const title = isExperience ? entry.item.title : entry.activity.title;
    const start = entry.planned_start;
    const end = isExperience ? entry.item.planned_end : entry.activity.planned_end;
    return [{
      id: isExperience ? entry.item.id : entry.activity.id,
      title: title ?? "Experience",
      // Keep the backend's sequence number, including gaps for entries that
      // remain in the text timeline but have no verified coordinates.
      sequence: entry.sequence_order,
      latitude: location.lat,
      longitude: location.lng,
      plannedStart: start,
      plannedEnd: end,
      category: isExperience ? entry.item.category_name ?? "Experience" : entry.activity.kind,
      itemState: isExperience ? entry.item.item_state : "ACTIVE",
      isLocked: isExperience ? entry.item.is_locked : false,
      kind: isExperience ? "experience" : "custom",
      locationLabel: isExperience ? entry.item.location_place_name : entry.activity.location_text,
    }];
  });
}

/** Route only adjacent timeline entries when both already have coordinates. */
export function buildConsecutiveRouteLegs(itinerary: ApiItinerary): MapRouteLeg[] {
  const entries = orderedTimelineEntries(itinerary);
  const legs: MapRouteLeg[] = [];

  for (let index = 1; index < entries.length; index += 1) {
    const previous = entries[index - 1];
    const current = entries[index];
    if (!previous || !current) continue;

    const fromLat = previous.kind === "experience" ? previous.item.location_latitude : previous.activity.latitude;
    const fromLng = previous.kind === "experience" ? previous.item.location_longitude : previous.activity.longitude;
    const toLat = current.kind === "experience" ? current.item.location_latitude : current.activity.latitude;
    const toLng = current.kind === "experience" ? current.item.location_longitude : current.activity.longitude;
    const origin = verifiedCoordinates(fromLat, fromLng);
    const destination = verifiedCoordinates(toLat, toLng);
    if (!origin || !destination) continue;

    legs.push({
      fromId: previous.kind === "experience" ? previous.item.id : previous.activity.id,
      toId: current.kind === "experience" ? current.item.id : current.activity.id,
      origin,
      destination,
    });
  }

  return legs;
}

export function itineraryFitBounds(
  points: Array<{ lat: number; lng: number }>,
  geometries: Array<GeoJSON.LineString | null> = [],
): [[number, number], [number, number]] | null {
  const coordinates: Array<[number, number]> = points.map(({ lat, lng }) => [lng, lat]);
  for (const geometry of geometries) {
    if (!geometry) continue;
    for (const coordinate of geometry.coordinates) {
      if (Number.isFinite(coordinate[0]) && Number.isFinite(coordinate[1])) {
        coordinates.push([coordinate[0], coordinate[1]]);
      }
    }
  }
  if (!coordinates.length) return null;

  let west = Math.min(...coordinates.map(([lng]) => lng));
  let east = Math.max(...coordinates.map(([lng]) => lng));
  let south = Math.min(...coordinates.map(([, lat]) => lat));
  let north = Math.max(...coordinates.map(([, lat]) => lat));

  // A single point or a perfectly horizontal/vertical route needs a small
  // extent so fitBounds remains predictable and does not zoom excessively.
  if (east - west < 0.01) {
    west -= 0.005;
    east += 0.005;
  }
  if (north - south < 0.01) {
    south -= 0.005;
    north += 0.005;
  }
  return [[west, south], [east, north]];
}
