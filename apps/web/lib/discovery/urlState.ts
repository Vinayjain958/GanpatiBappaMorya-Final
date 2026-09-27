import type { DiscoverySort } from "@/types/api";
import { DEFAULT_DISCOVERY_STATE, type DiscoveryDataSource, type DiscoveryState } from "@/types/discovery";

const VALID_SORTS: DiscoverySort[] = ["relevance", "distance", "price", "duration", "newest"];
const VALID_DATA_SOURCES: DiscoveryDataSource[] = ["all", "source", "demo"];

/** Parses shareable discovery state from the URL (?q=&category=&lat=&...).
 * Never includes anything sensitive — no tokens, no precise location
 * beyond what the user explicitly searched for. */
export function parseDiscoveryStateFromParams(params: URLSearchParams): DiscoveryState {
  const lat = params.has("lat") ? Number(params.get("lat")) : null;
  const lng = params.has("lng") ? Number(params.get("lng")) : null;
  const radiusKm = params.has("radius_km") ? Number(params.get("radius_km")) : null;
  const sortParam = params.get("sort");
  const dataSourceParam = params.get("data_source");

  return {
    q: params.get("q") ?? DEFAULT_DISCOVERY_STATE.q,
    category: params.get("category"),
    budget: (params.get("budget") as DiscoveryState["budget"]) ?? DEFAULT_DISCOVERY_STATE.budget,
    duration: (params.get("duration") as DiscoveryState["duration"]) ?? DEFAULT_DISCOVERY_STATE.duration,
    lat: lat != null && Number.isFinite(lat) ? lat : null,
    lng: lng != null && Number.isFinite(lng) ? lng : null,
    locationLabel: params.get("place") ?? null,
    radiusKm: radiusKm != null && Number.isFinite(radiusKm) ? radiusKm : null,
    sort: sortParam && VALID_SORTS.includes(sortParam as DiscoverySort) ? (sortParam as DiscoverySort) : "relevance",
    dataSource: dataSourceParam && VALID_DATA_SOURCES.includes(dataSourceParam as DiscoveryDataSource)
      ? dataSourceParam as DiscoveryDataSource
      : DEFAULT_DISCOVERY_STATE.dataSource,
  };
}

export function discoveryStateToParams(state: DiscoveryState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.category) params.set("category", state.category);
  if (state.budget !== "any") params.set("budget", state.budget);
  if (state.duration !== "any") params.set("duration", state.duration);
  if (state.lat != null) params.set("lat", String(state.lat));
  if (state.lng != null) params.set("lng", String(state.lng));
  if (state.locationLabel) params.set("place", state.locationLabel);
  if (state.radiusKm != null) params.set("radius_km", String(state.radiusKm));
  if (state.sort !== "relevance") params.set("sort", state.sort);
  if (state.dataSource !== "all") params.set("data_source", state.dataSource);
  return params;
}
