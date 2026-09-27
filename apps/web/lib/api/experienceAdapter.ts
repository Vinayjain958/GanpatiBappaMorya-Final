import type { ApiExperienceDetail, ApiExperienceSummary, ApiOpeningHourWindow, ApiRankedExperienceItem } from "@/types/api";
import type { Experience } from "@/types/experience";
import { haversineKm } from "@/lib/geo/haversine";

/** Reference point used only when no real query origin is available (e.g.
 * viewing an experience detail page with no location context set) — Fort,
 * Mumbai. Not a claim about the traveler's actual location. Prefer the
 * API's own `distance_km`/`travel_time_*` fields whenever present. */
const REFERENCE_POINT = { lat: 18.9346, lng: 72.8356 };

const CATEGORY_IMAGES: Record<string, string> = {
  "food-drink": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=800&q=80",
  "street-food": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=800&q=80",
  cafes: "https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=800&q=80",
  "culture-heritage": "https://images.unsplash.com/photo-1570168007204-dfb528c6958f?w=800&q=80",
  "art-galleries": "https://images.unsplash.com/photo-1531058020387-3be344556be6?w=800&q=80",
  museums: "https://images.unsplash.com/photo-1554907984-15263bfd63bd?w=800&q=80",
  workshops: "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=800&q=80",
  crafts: "https://images.unsplash.com/photo-1452860606245-08befc0ff44b?w=800&q=80",
  "shopping-markets": "https://images.unsplash.com/photo-1555529771-7888783a18d3?w=800&q=80",
  outdoors: "https://images.unsplash.com/photo-1580746738099-1e6c5aa54f88?w=800&q=80",
  adventure: "https://images.unsplash.com/photo-1502680390469-be75c86b636f?w=800&q=80",
  photography: "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=800&q=80",
  family: "https://images.unsplash.com/photo-1476703993599-0035a21b17a9?w=800&q=80",
  nightlife: "https://images.unsplash.com/photo-1470337458703-46ad1756a187?w=800&q=80",
  music: "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800&q=80",
  community: "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=800&q=80",
  "hidden-gems": "https://images.unsplash.com/photo-1521123845560-14093637aa7d?w=800&q=80",
  wellness: "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800&q=80",
  entertainment: "https://images.unsplash.com/photo-1489599162946-2f3f6b8b8b3f?w=800&q=80",
  "local-experiences": "https://images.unsplash.com/photo-1499892477393-f675706cbe6e?w=800&q=80",
};
const FALLBACK_IMAGE = "https://images.unsplash.com/photo-1499892477393-f675706cbe6e?w=800&q=80";

const STATUS_TO_AVAILABILITY: Record<string, Experience["availability"]> = {
  active: "available",
  draft: "limited",
  inactive: "unavailable",
};

const DAY_ABBREVIATIONS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatOpeningHours(windows: ApiOpeningHourWindow[] | undefined): string | null {
  if (!windows || windows.length === 0) return null;
  const openDays = windows.filter((w) => !w.is_closed && w.open_time && w.close_time);
  if (openDays.length === 0) return null;

  const uniqueWindows = new Set(openDays.map((w) => `${w.open_time}-${w.close_time}`));
  const days = openDays
    .map((w) => DAY_ABBREVIATIONS[w.day_of_week])
    .filter((d): d is string => Boolean(d));

  if (uniqueWindows.size === 1) {
    const [window] = uniqueWindows;
    const [open, close] = window.split("-");
    const dayLabel = days.length >= 6 ? "Daily" : days.join(", ");
    return `${dayLabel} ${open}–${close}`;
  }
  return `${days[0]} ${openDays[0].open_time}–${openDays[0].close_time} (varies by day)`;
}

function imageFromSummary(api: ApiExperienceSummary): Experience["image"] {
  const resolved = api.image;
  if (resolved?.url) {
    return {
      imageUrl: resolved.url,
      isFallback: false,
      isPlaceSpecific: resolved.is_place_specific ?? false,
      source: resolved.source,
      sourceUrl: resolved.source_url,
      license: resolved.license,
      author: resolved.author,
      attributionText: resolved.attribution_text,
    };
  }
  return {
    imageUrl: CATEGORY_IMAGES[api.category.slug] ?? FALLBACK_IMAGE,
    isFallback: true,
    isPlaceSpecific: false,
    source: null,
    sourceUrl: null,
    license: null,
    author: null,
    attributionText: null,
  };
}

function priceFromSummary(api: ApiExperienceSummary): number {
  if (api.price != null) return api.price;
  if (api.minimum_price != null) return api.minimum_price;
  return 0;
}

function isDetail(
  api: ApiExperienceSummary | ApiExperienceDetail | ApiRankedExperienceItem,
): api is ApiExperienceDetail {
  return "full_description" in api;
}

function isRanked(
  api: ApiExperienceSummary | ApiExperienceDetail | ApiRankedExperienceItem,
): api is ApiRankedExperienceItem {
  return "ranking_score" in api;
}

/** Optional fallback origin — when a discovery/detail request didn't
 * itself carry lat/lng (so the API returned distance_km: null), we can
 * still show an illustrative distance from a chosen origin (e.g. the
 * traveler's last-used discovery location) rather than nothing. Pass
 * `null` to leave distance genuinely absent. */
export function mapApiExperienceToUi(
  api: ApiExperienceSummary | ApiExperienceDetail | ApiRankedExperienceItem,
  fallbackOrigin: { lat: number; lng: number } | null = REFERENCE_POINT,
): Experience {
  const detail = isDetail(api) ? api : null;
  const ranked = isRanked(api) ? api : null;

  const distanceKm =
    api.distance_km ??
    (fallbackOrigin
      ? Math.round(
          haversineKm(fallbackOrigin.lat, fallbackOrigin.lng, api.location.latitude, api.location.longitude) * 10,
        ) / 10
      : null);
  const image = imageFromSummary(api);

  return {
    id: api.id,
    title: api.title,
    category: api.category.slug,
    categoryLabel: api.category.name,
    shortDescription: api.short_description,
    description: detail?.full_description ?? api.short_description,
    imageUrl: image.imageUrl,
    image,
    location: {
      area: api.location.locality ?? api.location.city,
      city: api.location.city,
      lat: api.location.latitude,
      lng: api.location.longitude,
    },
    distanceKm,
    travelTimeMinutes: api.travel_time_minutes,
    travelTimeSource: api.travel_time_source,
    durationMinutes: api.duration_minutes,
    priceInr: priceFromSummary(api),
    isPriceEstimated: api.is_price_estimated,
    rating: api.rating,
    reviewCount: api.review_count,
    provider: {
      id: api.provider.id,
      name: api.provider.business_name,
      verified: api.provider.verification_status === "verified",
    },
    tags: detail?.tags ?? [],
    accessibility: {
      wheelchairAccessible: detail?.wheelchair_accessible ?? null,
      stepFree: detail?.step_free ?? null,
      notes: detail?.accessibility_notes ?? undefined,
    },
    availability: STATUS_TO_AVAILABILITY[api.status] ?? "available",
    openingHours: detail ? formatOpeningHours(detail.opening_hours) : null,
    openingHoursWeekly: detail?.opening_hours
      ? detail.opening_hours.map((w) => ({
          day: DAY_ABBREVIATIONS[w.day_of_week] ?? `Day ${w.day_of_week}`,
          dayIndex: w.day_of_week,
          open: w.open_time,
          close: w.close_time,
          isClosed: w.is_closed,
          isSynthetic: w.is_synthetic,
        }))
      : undefined,
    isOpeningHoursSynthetic: detail?.opening_hours?.some((w) => w.is_synthetic) ?? false,
    availabilitySlots: detail?.availability_slots
      ? detail.availability_slots.map((s) => ({
          id: s.id,
          startTime: s.start_time,
          endTime: s.end_time,
          capacity: s.capacity,
          bookedCount: s.booked_count,
          isAvailable: s.is_available,
          isSynthetic: s.is_synthetic,
        }))
      : undefined,
    isAvailabilitySynthetic: detail?.availability_slots?.some((s) => s.is_synthetic) ?? false,
    reviews: detail?.reviews
      ? detail.reviews.map((r) => ({
          id: r.id,
          rating: r.rating_value,
          title: r.title,
          body: r.body,
          author: r.author_display_name,
          reviewedAt: r.reviewed_at,
          isSynthetic: r.is_synthetic,
        }))
      : undefined,
    ratingSummary: detail?.rating_summary
      ? {
          averageRating: detail.rating_summary.average_rating,
          reviewCount: detail.rating_summary.review_count,
          distribution: Object.fromEntries(
            Object.entries(detail.rating_summary.rating_distribution).map(([k, v]) => [
              parseInt(k, 10),
              v,
            ]),
          ),
          isSynthetic: detail.rating_summary.is_synthetic,
        }
      : null,
    highlights: [],
    isSynthetic: api.is_synthetic,
    matchSignals: ranked?.match_signals,
    personalized: ranked?.personalized,
  };
}
