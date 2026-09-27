import type { ApiItineraryItem } from "@/types/api";

const STORAGE_KEY = "localens.active-trip-progress.v1";
export const ACTIVE_TRIP_PROGRESS_EVENT = "localens:active-trip-progress";
const MAX_CROSS_PLATFORM_ROUTE_STOPS = 5;

export interface ActiveTripProgress {
  itineraryId: string;
  startedAt: string;
  completedItemIds: string[];
  status: "ACTIVE" | "COMPLETED";
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function storageKey(userId: string): string {
  return `${STORAGE_KEY}:${encodeURIComponent(userId)}`;
}

function publish(userId: string, progress: ActiveTripProgress | null): void {
  const storage = browserStorage();
  try {
    if (progress) storage?.setItem(storageKey(userId), JSON.stringify(progress));
    else storage?.removeItem(storageKey(userId));
  } catch {
    // Trip progress remains usable for this page when browser storage is disabled.
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(ACTIVE_TRIP_PROGRESS_EVENT));
  }
}

export function readActiveTripProgress(userId: string | null | undefined): ActiveTripProgress | null {
  if (!userId) return null;
  const storage = browserStorage();
  if (!storage) return null;
  try {
    const value: unknown = JSON.parse(storage.getItem(storageKey(userId)) ?? "null");
    if (!value || typeof value !== "object") return null;
    const candidate = value as Partial<ActiveTripProgress>;
    if (
      typeof candidate.itineraryId !== "string" ||
      typeof candidate.startedAt !== "string" ||
      !Array.isArray(candidate.completedItemIds) ||
      !candidate.completedItemIds.every((id) => typeof id === "string") ||
      (candidate.status !== "ACTIVE" && candidate.status !== "COMPLETED")
    ) return null;
    return {
      itineraryId: candidate.itineraryId,
      startedAt: candidate.startedAt,
      completedItemIds: candidate.completedItemIds,
      status: candidate.status,
    };
  } catch {
    return null;
  }
}

export function startActiveTrip(userId: string, itineraryId: string): ActiveTripProgress {
  const progress: ActiveTripProgress = {
    itineraryId,
    startedAt: new Date().toISOString(),
    completedItemIds: [],
    status: "ACTIVE",
  };
  publish(userId, progress);
  return progress;
}

export function clearActiveTripProgress(userId: string, itineraryId: string): void {
  const current = readActiveTripProgress(userId);
  if (current?.itineraryId === itineraryId) publish(userId, null);
}

export function completeActiveTripStop(
  userId: string,
  itineraryId: string,
  itemId: string,
  itineraryItemIds: string[],
): ActiveTripProgress | null {
  const current = readActiveTripProgress(userId);
  if (!current || current.itineraryId !== itineraryId || current.status !== "ACTIVE") return current;

  const completedItemIds = [...new Set([...current.completedItemIds, itemId])];
  const allStopsCompleted = itineraryItemIds.length > 0 && itineraryItemIds.every((id) => completedItemIds.includes(id));
  const next: ActiveTripProgress = {
    ...current,
    completedItemIds,
    status: allStopsCompleted ? "COMPLETED" : "ACTIVE",
  };
  publish(userId, next);
  return next;
}

export function getNextUncompletedStop<T extends { id: string }>(
  items: T[],
  progress: ActiveTripProgress | null,
): T | null {
  if (!progress || progress.status !== "ACTIVE") return null;
  const completed = new Set(progress.completedItemIds);
  return items.find((item) => !completed.has(item.id)) ?? null;
}

function validCoordinate(latitude: number | null, longitude: number | null): boolean {
  return latitude != null && longitude != null && Number.isFinite(latitude) && Number.isFinite(longitude) &&
    latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180;
}

export function countStopsWithoutCoordinates(items: ApiItineraryItem[]): number {
  return items.filter((item) => !validCoordinate(item.location_latitude, item.location_longitude)).length;
}

export function countStopsBeyondMapsRouteLimit(items: ApiItineraryItem[]): number {
  const verifiedStopCount = items.filter((item) => validCoordinate(item.location_latitude, item.location_longitude)).length;
  return Math.max(0, verifiedStopCount - MAX_CROSS_PLATFORM_ROUTE_STOPS);
}

export interface GoogleMapsRouteStop {
  latitude: number | null;
  longitude: number | null;
  locationText?: string | null;
  travelMode?: string | null;
}

function googleTravelMode(mode: string | null): string | null {
  if (mode === "driving" || mode === "walking") return mode;
  if (mode === "cycling") return "bicycling";
  if (mode === "transit") return "transit";
  return null;
}

export function buildGoogleMapsDirectionsUrlFromStops(
  stops: GoogleMapsRouteStop[],
  startingPoint?: string | null,
): string | null {
  const origin = startingPoint?.trim() || null;
  // Keep an explicit origin plus the itinerary stops inside the five-stop
  // cross-platform route size (Google Maps mobile supports three waypoints).
  const stopLimit = origin ? MAX_CROSS_PLATFORM_ROUTE_STOPS - 1 : MAX_CROSS_PLATFORM_ROUTE_STOPS;
  const routeStops = stops.filter((stop) =>
    validCoordinate(stop.latitude, stop.longitude) || Boolean(stop.locationText?.trim()),
  ).slice(0, stopLimit);
  if (!routeStops.length) return null;

  const point = (stop: GoogleMapsRouteStop) =>
    validCoordinate(stop.latitude, stop.longitude)
      ? `${stop.latitude},${stop.longitude}`
      : stop.locationText!.trim();
  if (routeStops.length === 1 && !origin) {
    const url = new URL("https://www.google.com/maps/search/");
    url.searchParams.set("api", "1");
    url.searchParams.set("query", point(routeStops[0]));
    return url.toString();
  }

  const url = new URL("https://www.google.com/maps/dir/");
  url.searchParams.set("api", "1");
  url.searchParams.set("origin", origin ?? point(routeStops[0]));
  url.searchParams.set("destination", point(routeStops[routeStops.length - 1]));
  const waypoints = routeStops.slice(origin ? 0 : 1, -1).map(point);
  if (waypoints.length) url.searchParams.set("waypoints", waypoints.join("|"));

  const modes = [...new Set(routeStops.map((item) => googleTravelMode(item.travelMode ?? null)).filter(Boolean))];
  const mode = modes[0];
  if (modes.length === 1 && mode) url.searchParams.set("travelmode", mode);
  return url.toString();
}

export function buildGoogleMapsDirectionsUrl(
  items: ApiItineraryItem[],
  startingPoint?: string | null,
): string | null {
  const ordered = [...items].sort((left, right) => left.sequence_order - right.sequence_order);
  return buildGoogleMapsDirectionsUrlFromStops(
    ordered.map((item) => ({
      latitude: item.location_latitude,
      longitude: item.location_longitude,
      travelMode: item.travel_mode,
    })),
    startingPoint,
  );
}
