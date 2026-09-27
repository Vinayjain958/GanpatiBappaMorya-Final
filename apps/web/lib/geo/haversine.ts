/**
 * Straight-line ("as the crow flies") distance in kilometers — NOT
 * travel time or routed distance. Mirrors apps/api/src/core/geo.py so
 * both sides agree on the formula; the single source of truth for any
 * server-computed distance is still the backend response (`distance_km`
 * on an experience result), this is only for client-side display math
 * (e.g. quick map-viewport reasoning) that doesn't need a round trip.
 */
const EARTH_RADIUS_KM = 6371.0088;

export function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return EARTH_RADIUS_KM * 2 * Math.asin(Math.sqrt(a));
}
