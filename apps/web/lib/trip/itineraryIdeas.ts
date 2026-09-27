import { haversineKm } from "@/lib/geo/haversine";
import type { ApiExperienceSummary } from "@/types/api";

export interface ItineraryIdea {
  id: string;
  title: string;
  locality: string | null;
  city: string;
  experienceIds: string[];
  experienceTitles: string[];
  categories: string[];
  visitMinutes: number | null;
  estimatedBudget: number | null;
  hasEstimatedPrice: boolean;
  routeDistanceKm: number;
  travelEstimateMinutes: number;
}

export interface ItineraryIdeaOptions {
  maxIdeas?: number;
  maxIdeasPerLocation?: number;
  maxStops?: number;
  maxBudget?: number;
  availableMinutes?: number;
}

const MAX_AREA_DISTANCE_KM = 10;
const CITY_SPEED_KM_PER_HOUR = 18;
const MAX_STOPS_PER_IDEA = 4;
const TRUSTED_RATING_SOURCES = new Set([
  "verified_reviews",
  "trusted_reviews",
  "provider_verified",
]);

function knownPrice(experience: ApiExperienceSummary): number | null {
  return experience.price ?? experience.maximum_price ?? experience.minimum_price ?? null;
}

function popularityScore(experience: ApiExperienceSummary): number {
  if (
    !experience.rating_source || !TRUSTED_RATING_SOURCES.has(experience.rating_source) ||
    experience.rating == null || !experience.review_count
  ) return 0;
  const rating = Math.max(0, Math.min(5, experience.rating)) / 5;
  const reviews = Math.min(1, Math.log10(experience.review_count + 1) / 3);
  return rating * 0.65 + reviews * 0.35;
}

function distanceKm(first: ApiExperienceSummary, second: ApiExperienceSummary): number {
  return haversineKm(
    first.location.latitude,
    first.location.longitude,
    second.location.latitude,
    second.location.longitude,
  );
}

function estimatedTravelMinutes(distance: number): number {
  return Math.ceil((distance / CITY_SPEED_KM_PER_HOUR) * 60);
}

function routeMetrics(experiences: ApiExperienceSummary[]) {
  let routeDistanceKm = 0;
  for (let index = 1; index < experiences.length; index += 1) {
    routeDistanceKm += distanceKm(experiences[index - 1], experiences[index]);
  }
  return {
    routeDistanceKm: Math.round(routeDistanceKm * 10) / 10,
    travelEstimateMinutes: estimatedTravelMinutes(routeDistanceKm),
  };
}

function toIdea(experiences: ApiExperienceSummary[], variation: number): ItineraryIdea {
  const ids = experiences.map((experience) => experience.id);
  const localities = experiences.map((experience) => experience.location.locality).filter(Boolean);
  const locality = localities[0] ?? null;
  const city = experiences[0].location.city;
  const categories = [...new Set(experiences.map((experience) => experience.category.name))];
  const prices = experiences.map(knownPrice);
  const durations = experiences.map((experience) => experience.duration_minutes);
  const allPricesKnown = prices.every((price): price is number => price != null);
  const allDurationsKnown = durations.every((duration): duration is number => duration != null);
  const route = routeMetrics(experiences);

  return {
    id: `idea-${variation}-${ids.join("-")}`,
    title: `${locality ?? city} · ${variation === 0 ? "Local favorites" : "Nearby mix"}`,
    locality,
    city,
    experienceIds: ids,
    experienceTitles: experiences.map((experience) => experience.title),
    categories,
    visitMinutes: allDurationsKnown ? durations.reduce((total, duration) => total + duration, 0) : null,
    estimatedBudget: allPricesKnown ? prices.reduce((total, price) => total + price, 0) : null,
    hasEstimatedPrice: experiences.some((experience) => experience.is_price_estimated),
    ...route,
  };
}

function routeFromSeed(
  group: ApiExperienceSummary[],
  seed: ApiExperienceSummary,
  options: Required<Pick<ItineraryIdeaOptions, "maxStops" | "maxBudget" | "availableMinutes">>,
): ApiExperienceSummary[] {
  const route = [seed];
  const usedIds = new Set([seed.id]);
  let knownCost = knownPrice(seed) ?? 0;
  let knownVisitMinutes = seed.duration_minutes ?? 90;
  let routeDistance = 0;

  while (route.length < options.maxStops) {
    const previous = route[route.length - 1];
    const usedCategories = new Set(route.map((experience) => experience.category.slug));
    const ranked = group
      .filter((candidate) => !usedIds.has(candidate.id))
      .map((candidate) => {
        const legDistance = distanceKm(previous, candidate);
        const price = knownPrice(candidate);
        const duration = candidate.duration_minutes ?? 90;
        const budgetOverflow = options.maxBudget >= 0 && price != null && knownCost + price > options.maxBudget;
        const nextRouteDistance = routeDistance + legDistance;
        const nextVisit = knownVisitMinutes + duration;
        const nextTravel = estimatedTravelMinutes(nextRouteDistance);
        const timeOverflow = options.availableMinutes > 0 && nextVisit + nextTravel > options.availableMinutes;
        const repeatedCategory = usedCategories.has(candidate.category.slug);
        const score =
          (legDistance / MAX_AREA_DISTANCE_KM) * 0.52 +
          (Math.min(duration, 240) / 240) * 0.18 +
          (price == null ? 0.5 : Math.min(price, 5000) / 5000) * 0.14 +
          (repeatedCategory ? 0.12 : 0) -
          popularityScore(candidate) * 0.04;
        return { candidate, legDistance, price, duration, budgetOverflow, timeOverflow, score };
      })
      .filter((item) => item.legDistance <= MAX_AREA_DISTANCE_KM && !item.budgetOverflow && !item.timeOverflow)
      .sort((first, second) => first.score - second.score || first.candidate.id.localeCompare(second.candidate.id));

    const next = ranked[0];
    if (!next) break;
    route.push(next.candidate);
    usedIds.add(next.candidate.id);
    knownCost += next.price ?? 0;
    knownVisitMinutes += next.duration;
    routeDistance += next.legDistance;
  }
  return route;
}

function planLocation(
  group: ApiExperienceSummary[],
  options: Required<Pick<ItineraryIdeaOptions, "maxIdeasPerLocation" | "maxStops" | "maxBudget" | "availableMinutes">>,
): ItineraryIdea[] {
  if (!group.length) return [];
  const latitude = group.reduce((sum, item) => sum + item.location.latitude, 0) / group.length;
  const longitude = group.reduce((sum, item) => sum + item.location.longitude, 0) / group.length;
  const centralSeed = [...group].sort((first, second) => {
    const firstDistance = haversineKm(latitude, longitude, first.location.latitude, first.location.longitude);
    const secondDistance = haversineKm(latitude, longitude, second.location.latitude, second.location.longitude);
    return firstDistance - secondDistance || first.id.localeCompare(second.id);
  })[0];
  const alternateSeed = [...group]
    .filter((item) => item.id !== centralSeed.id)
    .sort((first, second) => {
      const scoreDifference = popularityScore(second) - popularityScore(first);
      if (scoreDifference !== 0) return scoreDifference;
      return distanceKm(second, centralSeed) - distanceKm(first, centralSeed) || first.id.localeCompare(second.id);
    })[0];

  const seeds = [centralSeed, alternateSeed].filter((item): item is ApiExperienceSummary => Boolean(item))
    .slice(0, options.maxIdeasPerLocation);
  const ideas: ItineraryIdea[] = [];
  const seenRoutes = new Set<string>();
  for (const [variation, seed] of seeds.entries()) {
    const route = routeFromSeed(group, seed, options);
    const key = route.map((item) => item.id).join("\u0000");
    if (seenRoutes.has(key)) continue;
    seenRoutes.add(key);
    ideas.push(toIdea(route, variation));
  }
  return ideas;
}

/**
 * Builds one or two short, distance-aware suggestions for every locality in
 * the real catalog results. The weighted greedy route favors nearby stops,
 * manageable visit times and costs, category variety, and only uses ratings
 * when the catalog marks their source as trusted. Suggestions are estimates;
 * the preview/compose APIs remain authoritative for date, hours, availability,
 * budget and routed travel checks.
 */
export function buildItineraryIdeas(
  experiences: ApiExperienceSummary[],
  optionsOrMaxIdeas: ItineraryIdeaOptions | number = {},
): ItineraryIdea[] {
  const options = typeof optionsOrMaxIdeas === "number"
    ? { maxIdeas: optionsOrMaxIdeas }
    : optionsOrMaxIdeas;
  const maxIdeas = options.maxIdeas ?? 200;
  if (!Number.isInteger(maxIdeas) || maxIdeas <= 0) return [];

  const maxIdeasPerLocation = Math.max(1, Math.min(2, options.maxIdeasPerLocation ?? 2));
  const maxStops = Math.max(1, Math.min(MAX_STOPS_PER_IDEA, options.maxStops ?? MAX_STOPS_PER_IDEA));
  const maxBudget = options.maxBudget != null && Number.isFinite(options.maxBudget) ? options.maxBudget : -1;
  const availableMinutes = options.availableMinutes != null && Number.isFinite(options.availableMinutes)
    ? options.availableMinutes
    : 0;
  const groups = new Map<string, ApiExperienceSummary[]>();
  const seenIds = new Set<string>();

  for (const experience of experiences) {
    const { latitude, longitude, locality, city } = experience.location;
    if (
      experience.is_synthetic || !experience.id || seenIds.has(experience.id) ||
      !Number.isFinite(latitude) || !Number.isFinite(longitude)
    ) continue;
    seenIds.add(experience.id);
    const key = `${city}\u0000${locality ?? city}`;
    groups.set(key, [...(groups.get(key) ?? []), experience]);
  }

  return [...groups.entries()]
    .sort(([first], [second]) => first.localeCompare(second))
    .flatMap(([, group]) => planLocation(group, { maxIdeasPerLocation, maxStops, maxBudget, availableMinutes }))
    .slice(0, maxIdeas);
}
