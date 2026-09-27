"""ExperienceDiscoveryService — Phase 4 basic catalog discovery.

Deliberately NOT ranking/personalization/AI: relevance is a small,
explainable deterministic score (see `_relevance_score`), never called
"AI ranked" or "recommended for you" anywhere in the API or UI copy
(docs/AI_CONTEXT.md — Phase 7 owns real personalization).

Geospatial strategy (docs/DECISIONS.md ADR-023): a bounding box narrows
the SQL query first (portable — no PostGIS/SQLite spatial extensions),
then exact Haversine distance is computed here in Python and used to
both filter to the requested radius and sort by distance. This is fine
for the current catalog size (~350 rows); a future phase should move to
a spatial index if the catalog grows by orders of magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.config import Settings
from src.core.geo import bounding_box, haversine_km, validate_coordinates
from src.models.experience import Experience
from src.repositories.experience_repository import ExperienceFilters, ExperienceRepository
from src.services.search_understanding import text_match_score

Sort = str  # "relevance" | "distance" | "price" | "duration" | "newest"

# Deterministic keyword relevance weights — NOT machine learning. A field
# either contains the (lowercased) query substring or it doesn't; matches
# are summed. Documented here so the scoring is auditable.
_RELEVANCE_WEIGHTS = {
    "title": 3.0,
    "category": 2.0,
    "locality": 1.5,
    "city": 1.0,
    "short_description": 1.0,
    "full_description": 0.5,
}
_TRUSTED_RATING_SOURCES = {"verified_reviews", "trusted_reviews", "provider_verified"}


@dataclass
class DiscoveryQuery:
    q: str | None = None
    category_slug: str | None = None
    city: str | None = None
    locality: str | None = None
    provider_id: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_duration_minutes: int | None = None
    max_duration_minutes: int | None = None
    source_type: str | None = None
    is_synthetic: bool | None = None
    status: str | None = "active"
    lat: float | None = None
    lng: float | None = None
    radius_km: float | None = None
    sort: Sort = "relevance"
    limit: int = 20
    offset: int = 0


@dataclass
class DiscoveryItem:
    experience: Experience
    distance_km: float | None


@dataclass
class DiscoveryResult:
    items: list[DiscoveryItem]
    total: int


@dataclass
class _ScoredItem:
    experience: Experience
    distance_km: float | None
    relevance: float


def _effective_price(experience: Experience) -> float | None:
    if experience.price is not None:
        return experience.price
    return experience.minimum_price


def _lexical_score(experience: Experience, query: str) -> float:
    if not query.strip():
        return 0.0
    fields = (
        (experience.title, _RELEVANCE_WEIGHTS["title"]),
        (f"{experience.category.name} {experience.category.slug}", _RELEVANCE_WEIGHTS["category"]),
        (experience.location.locality or "", _RELEVANCE_WEIGHTS["locality"]),
        (experience.location.city, _RELEVANCE_WEIGHTS["city"]),
        (experience.short_description, _RELEVANCE_WEIGHTS["short_description"]),
        (experience.full_description, _RELEVANCE_WEIGHTS["full_description"]),
        (" ".join(experience.tags or []), 0.8),
    )
    total_weight = sum(weight for _, weight in fields)
    return sum(text_match_score(query, text) * weight for text, weight in fields) / total_weight


def _relevance_score(
    experience: Experience, query: str, distance_km: float | None, lexical: float | None = None
) -> float:
    """Combine query understanding with evidence-backed quality/location.

    The rating contribution is zero for synthetic/demo ratings. This is a
    deterministic catalog score, not traveler personalization or an AI claim.
    """
    if lexical is None:
        lexical = _lexical_score(experience, query)

    rating_source = getattr(experience, "rating_source", None)
    rating = getattr(experience, "rating", None)
    review_count = getattr(experience, "review_count", None) or 0
    trusted_rating = rating_source in _TRUSTED_RATING_SOURCES and rating is not None and review_count > 0
    popularity = 0.0
    if trusted_rating:
        import math

        volume_confidence = min(1.0, math.log1p(review_count) / math.log(51))
        popularity = max(0.0, min(1.0, (float(rating) / 5.0) * volume_confidence))

    completeness = sum((
        getattr(experience, "price", None) is not None or getattr(experience, "minimum_price", None) is not None,
        getattr(experience, "duration_minutes", None) is not None,
        getattr(experience, "opening_hours_status", "unavailable") != "unavailable",
    )) / 3
    proximity = 0.0 if distance_km is None else 1.0 / (1.0 + distance_km / 5.0)
    # Query relevance dominates. Verified popularity, nearby distance, and
    # known visit facts refine the order without inventing a signal.
    return (0.70 * lexical) + (0.15 * popularity) + (0.10 * proximity) + (0.05 * completeness)


def _sort_items(items: list[_ScoredItem], sort: Sort, has_query: bool) -> list[_ScoredItem]:
    if sort == "distance":
        return sorted(items, key=lambda i: (i.distance_km is None, i.distance_km))
    if sort == "price":
        return sorted(
            items,
            key=lambda i: (_effective_price(i.experience) is None, _effective_price(i.experience) or 0),
        )
    if sort == "duration":
        return sorted(
            items,
            key=lambda i: (i.experience.duration_minutes is None, i.experience.duration_minutes or 0),
        )
    if sort == "newest":
        return sorted(items, key=lambda i: i.experience.created_at, reverse=True)

    # "relevance" (default): the deterministic combined score above —
    # lexical intent dominates, with trusted rating evidence and completeness
    # contributing when available. This is never called personalized/ML order.
    if has_query:
        return sorted(items, key=lambda i: (i.relevance, i.experience.created_at), reverse=True)
    return sorted(
        items,
        key=lambda i: (
            i.relevance,
            getattr(i.experience, "rating", None) or 0,
            getattr(i.experience, "created_at", None),
        ),
        reverse=True,
    )


class ExperienceDiscoveryService:
    def __init__(
        self, repository: ExperienceRepository, settings: Settings, *, include_schedule: bool = True
    ) -> None:
        self._repository = repository
        self._settings = settings
        # False only for callers that never touch opening hours/availability
        # on the returned experiences (the plain catalog list endpoint).
        self._include_schedule = include_schedule

    async def search(self, query: DiscoveryQuery) -> DiscoveryResult:
        has_location = query.lat is not None and query.lng is not None
        if has_location:
            validate_coordinates(query.lat, query.lng)  # type: ignore[arg-type]
        if query.radius_km is not None:
            if not has_location:
                raise ValueError("radius_km requires both lat and lng")
            if not 0 < query.radius_km <= self._settings.discovery_max_radius_km:
                raise ValueError(
                    f"radius_km must be between 0 and {self._settings.discovery_max_radius_km}"
                )
        if query.sort == "distance" and not has_location:
            raise ValueError("sort=distance requires both lat and lng")
        if query.limit < 1 or query.limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if query.offset < 0:
            raise ValueError("offset must be >= 0")

        filters = ExperienceFilters(
            category_slug=query.category_slug,
            city=query.city,
            locality=query.locality,
            provider_id=query.provider_id,
            min_price=query.min_price,
            max_price=query.max_price,
            min_duration_minutes=query.min_duration_minutes,
            max_duration_minutes=query.max_duration_minutes,
            source_type=query.source_type,
            is_synthetic=query.is_synthetic,
            status=query.status,
        )
        if has_location and query.radius_km:
            box = bounding_box(query.lat, query.lng, query.radius_km)  # type: ignore[arg-type]
            filters.min_lat, filters.max_lat = box.min_lat, box.max_lat
            filters.min_lng, filters.max_lng = box.min_lng, box.max_lng

        candidates = await self._repository.search(
            filters, cap=self._settings.discovery_candidate_cap, include_schedule=self._include_schedule
        )

        scored: list[_ScoredItem] = []
        for experience in candidates:
            lexical_match = _lexical_score(experience, query.q) if query.q else 0.0
            if query.q and lexical_match <= 0:
                continue

            distance_km: float | None = None
            if has_location:
                distance_km = round(
                    haversine_km(
                        query.lat,  # type: ignore[arg-type]
                        query.lng,  # type: ignore[arg-type]
                        experience.location.latitude,
                        experience.location.longitude,
                    ),
                    2,
                )
                if query.radius_km is not None and distance_km > query.radius_km:
                    continue

            combined = _relevance_score(experience, query.q or "", distance_km, lexical=lexical_match)
            scored.append(_ScoredItem(experience=experience, distance_km=distance_km, relevance=combined))

        scored = _sort_items(scored, query.sort, bool(query.q))
        total = len(scored)
        page = scored[query.offset : query.offset + query.limit]

        return DiscoveryResult(
            items=[DiscoveryItem(experience=i.experience, distance_km=i.distance_km) for i in page],
            total=total,
        )
