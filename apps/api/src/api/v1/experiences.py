from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.embedding import EmbeddingAdapter
from src.adapters.errors import AdapterError
from src.adapters.routing import OSRMRoutingAdapter, RoutingAdapter
from src.core.config import Settings, get_settings
from src.core.db import get_session
from src.core.deps import CurrentProvider, CurrentUser, require_traveler
from src.core.embedding import get_embedding_adapter
from src.core.errors import ApiError
from src.core.location import get_routing_adapter
from src.models.experience import Experience
from src.models.provider import Provider
from src.models.user import User
from src.repositories.experience_repository import ExperienceRepository
from src.repositories.interaction_repository import InteractionRepository
from src.repositories.review_repository import ReviewRepository
from src.schemas.experience import (
    AvailabilitySlotSummary,
    ExperienceDetail,
    ExperienceListResponse,
    ExperienceReviewListResponse,
    ExperienceReviewSummary,
    ExperienceSummary,
    RatingSummary,
)
from src.schemas.experience_write import ExperienceCreateRequest, ExperienceUpdateRequest
from src.schemas.semantic_search import (
    ExcludedReasonSummary,
    SemanticSearchItem,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from src.schemas.source_data import (
    OverturePlaceDatasetRecord,
    OverturePlaceDatasetResponse,
    OverturePlaceEnrichment,
    OverturePlaceSourceRecord,
)
from src.services import experience as experience_service
from src.services.discovery import DiscoveryQuery, ExperienceDiscoveryService
from src.services.discovery_pipeline import DiscoveryPipelineService

router = APIRouter(prefix="/experiences", tags=["experiences"])

SortParam = Literal["relevance", "distance", "price", "duration", "newest"]

_OVERTURE_SOURCE_FIELDS = (
    "source_record_id", "source_place_record_id", "source_name", "source_license",
    "source_version", "source_url", "source_confidence", "name", "overture_category",
    "operating_status", "latitude", "longitude", "address", "locality", "city", "state",
    "postal_code", "country",
)
_LOCALENS_ENRICHMENT_FIELDS = (
    "normalized_name", "category_slug", "estimated_duration_minutes",
    "estimated_price_low", "estimated_price_high",
)


@lru_cache(maxsize=1)
def _load_overture_dataset() -> OverturePlaceDatasetResponse:
    data_path = Path(__file__).resolve().parents[5] / "data" / "processed" / "overture_experiences.json"
    try:
        with data_path.open(encoding="utf-8") as source_file:
            raw_records = json.load(source_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ApiError("Overture source snapshot is unavailable.", status_code=503) from exc

    if not isinstance(raw_records, list):
        raise ApiError("Overture source snapshot is invalid.", status_code=503)
    source_rows = [
        record for record in raw_records
        if isinstance(record, dict) and record.get("source_type") == "overture_places"
    ]
    if not source_rows:
        raise ApiError("Overture source snapshot is empty.", status_code=503)

    versions = sorted({str(record.get("source_version")) for record in source_rows if record.get("source_version")})
    records: list[OverturePlaceDatasetRecord] = []
    try:
        for record in source_rows:
            records.append(
                OverturePlaceDatasetRecord(
                    source_record={key: record.get(key) for key in _OVERTURE_SOURCE_FIELDS},
                    localens_enrichment={key: record.get(key) for key in _LOCALENS_ENRICHMENT_FIELDS},
                )
            )
    except ValueError as exc:
        raise ApiError("Overture source snapshot failed validation.", status_code=503) from exc

    version = versions[0] if len(versions) == 1 else ", ".join(versions)
    return OverturePlaceDatasetResponse(
        source="Overture Maps Places",
        snapshot_version=version,
        is_live=False,
        record_count=len(records),
        synthetic_records_included=False,
        attribution_note=(
            "Source fields retain each record's provider, license, version, and source ID. "
            "LocaLens normalization and estimated price/duration are separated from source facts. "
            "This is a downloaded snapshot, not a live feed."
        ),
        records=records,
    )


@lru_cache(maxsize=1)
def _load_overture_catalog_addon() -> OverturePlaceDatasetResponse:
    """Load the larger, provenance-filtered catalog snapshot.

    This is separate from the original raw source snapshot because the
    archived normalized catalog does not retain Overture's raw primary
    category or operating-status fields for every row. Those values stay
    null instead of being reconstructed or guessed.
    """
    data_path = Path(__file__).resolve().parents[5] / "data" / "processed" / "overture_catalog_addon.json"
    try:
        with data_path.open(encoding="utf-8") as source_file:
            raw_records = json.load(source_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ApiError("Expanded Overture catalog snapshot is unavailable.", status_code=503) from exc

    if not isinstance(raw_records, list) or not raw_records:
        raise ApiError("Expanded Overture catalog snapshot is invalid.", status_code=503)

    records: list[OverturePlaceDatasetRecord] = []
    try:
        for record in raw_records:
            if not isinstance(record, dict) or record.get("source_type") != "overture_places":
                raise ValueError("Unexpected record in Overture catalog snapshot.")
            records.append(
                OverturePlaceDatasetRecord(
                    source_record=OverturePlaceSourceRecord(
                        source_record_id=record["source_record_id"],
                        source_place_record_id=record.get("source_place_record_id"),
                        source_name=record["source_name"],
                        source_license=record["source_license"],
                        source_version=record["source_version"],
                        source_url=record["source_url"],
                        source_confidence=record.get("source_confidence"),
                        name=record["name"],
                        overture_category=None,
                        operating_status=None,
                        latitude=record["latitude"],
                        longitude=record["longitude"],
                        address=record.get("address"),
                        locality=record.get("locality"),
                        city=record.get("city"),
                        state=record.get("state"),
                        postal_code=record.get("postal_code"),
                        country=record.get("country"),
                    ),
                    localens_enrichment=OverturePlaceEnrichment(
                        normalized_name=record["normalized_name"],
                        category_slug=record["category_slug"],
                        estimated_duration_minutes=record.get("estimated_duration_minutes"),
                        estimated_price_low=record.get("estimated_price_low"),
                        estimated_price_high=record.get("estimated_price_high"),
                    ),
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError("Expanded Overture catalog snapshot failed validation.", status_code=503) from exc

    versions = sorted({record.source_record.source_version for record in records})
    return OverturePlaceDatasetResponse(
        source="Overture Maps Places",
        snapshot_version=", ".join(versions),
        is_live=False,
        record_count=len(records),
        synthetic_records_included=False,
        attribution_note=(
            "This normalized catalog snapshot contains only non-synthetic Overture-derived records, "
            "with per-record source IDs, source names, licenses, versions, and URLs. LocaLens category "
            "mapping and estimates are separated under localens_enrichment. The archived catalog did not "
            "retain Overture primary-category or operating-status values for these rows; those fields are "
            "null. It is not a full raw Overture dump and is not a live feed."
        ),
        records=records,
    )


@router.get("", response_model=ExperienceListResponse)
async def list_experiences(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
    q: Annotated[str | None, Query(max_length=200, description="Keyword search")] = None,
    category: Annotated[str | None, Query(description="Category slug filter")] = None,
    city: Annotated[str | None, Query()] = None,
    locality: Annotated[str | None, Query()] = None,
    provider: Annotated[str | None, Query(description="Provider id filter")] = None,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_duration_minutes: Annotated[int | None, Query(ge=0)] = None,
    max_duration_minutes: Annotated[int | None, Query(ge=0)] = None,
    source_type: Annotated[str | None, Query()] = None,
    is_synthetic: Annotated[bool | None, Query()] = None,
    status: Annotated[str, Query(description="Experience status filter")] = "active",
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[float | None, Query(gt=0)] = None,
    sort: Annotated[SortParam, Query()] = "relevance",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExperienceListResponse:
    repository = ExperienceRepository(session)
    service = ExperienceDiscoveryService(repository, settings)

    try:
        result = await service.search(
            DiscoveryQuery(
                q=q, category_slug=category, city=city, locality=locality, provider_id=provider,
                min_price=min_price, max_price=max_price,
                min_duration_minutes=min_duration_minutes, max_duration_minutes=max_duration_minutes,
                source_type=source_type, is_synthetic=is_synthetic, status=status,
                lat=lat, lng=lng, radius_km=radius_km, sort=sort, limit=limit, offset=offset,
            )
        )
    except ValueError as exc:
        raise ApiError(str(exc), status_code=422) from exc

    summaries = [ExperienceSummary.model_validate(item.experience) for item in result.items]
    for summary, item in zip(summaries, result.items, strict=True):
        summary.distance_km = item.distance_km

    # Travel-time enrichment is applied only to the returned page (never
    # the whole catalog) and only when a travel origin was given — see
    # docs/DECISIONS.md ADR-023. OSRM failures degrade to "unavailable"
    # per item rather than breaking the whole discovery response.
    if lat is not None and lng is not None and summaries:
        destinations = [
            (s.id, item.experience.location.latitude, item.experience.location.longitude)
            for s, item in zip(summaries, result.items, strict=True)
        ][: settings.osrm_max_matrix_destinations]
        try:
            entries = await routing.get_travel_time_matrix(
                (lat, lng), destinations, profile=settings.osrm_profile
            )
            source = "osrm" if isinstance(routing, OSRMRoutingAdapter) else "haversine_estimate"
            by_id = {e.id: e for e in entries}
            for summary in summaries:
                entry = by_id.get(summary.id)
                if entry is not None and entry.duration_minutes is not None:
                    summary.travel_time_minutes = entry.duration_minutes
                    summary.travel_time_source = source
        except AdapterError:
            pass  # travel time is an enhancement; discovery must still succeed

    return ExperienceListResponse(items=summaries, total=result.total, limit=limit, offset=offset)


@router.post("/semantic-search", response_model=SemanticSearchResponse)
async def semantic_search(
    payload: SemanticSearchRequest,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedding_adapter: Annotated[EmbeddingAdapter, Depends(get_embedding_adapter)],
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
) -> SemanticSearchResponse:
    """Semantic retrieval -> deterministic feasibility gate (Phase 6).
    Only FEASIBLE candidates are ever returned in `items` — see
    DiscoveryPipelineService. retrieval_mode is always honestly reported
    (never claims pgvector/semantic retrieval happened when it fell back
    to keyword search)."""
    pipeline = DiscoveryPipelineService(session, settings, embedding_adapter, routing)
    try:
        result = await pipeline.run(
            raw_query=payload.query,
            interests=payload.interests or None,
            category_slug=payload.category_slug,
            city=payload.city,
            locality=payload.locality,
            location_text=payload.location_text,
            constraints=payload.constraints,
            limit=payload.limit,
            travel_profile=settings.osrm_profile,
        )
    except ValueError as exc:
        raise ApiError(str(exc), status_code=422) from exc

    experience_repo = ExperienceRepository(session)
    items: list[SemanticSearchItem] = []
    for pipeline_item in result.items:
        experience = await experience_repo.get_by_id(pipeline_item.experience_id)
        if experience is None:
            continue
        items.append(
            SemanticSearchItem(
                experience=ExperienceSummary.model_validate(experience),
                semantic_similarity=pipeline_item.similarity,
            )
        )

    return SemanticSearchResponse(
        items=items,
        retrieval_mode=result.retrieval_mode,
        candidate_count=result.candidate_count,
        feasible_count=result.feasible_count,
        excluded_count=result.excluded_count,
        excluded_summary=ExcludedReasonSummary(
            reason_counts=result.excluded_summary.reason_counts,
            sample=result.excluded_summary.sample,
        ),
    )


@router.get("/source-data/overture", response_model=OverturePlaceDatasetResponse)
async def get_overture_source_data() -> OverturePlaceDatasetResponse:
    """Download the non-synthetic Overture snapshot with per-record provenance."""
    return _load_overture_dataset()


@router.get("/source-data/overture/catalog", response_model=OverturePlaceDatasetResponse)
async def get_overture_catalog_addon() -> OverturePlaceDatasetResponse:
    """Download the expanded normalized catalog without demo or user rows."""
    return _load_overture_catalog_addon()


@router.get("/saved", response_model=ExperienceListResponse)
async def list_saved_experiences(
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExperienceListResponse:
    """List the authenticated traveler's current bookmarks from SAVE/UNSAVE events."""
    saved_ids = await InteractionRepository(session).get_saved_experience_ids(user.traveler.id)
    page_ids = saved_ids[offset : offset + limit]
    rows = await ExperienceRepository(session).list_by_ids(page_ids)
    rows_by_id = {row.id: row for row in rows}
    ordered_rows = [rows_by_id[experience_id] for experience_id in page_ids if experience_id in rows_by_id]
    return ExperienceListResponse(
        items=[ExperienceSummary.model_validate(row) for row in ordered_rows],
        total=len(saved_ids),
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ExperienceDetail, status_code=201)
async def create_experience(
    payload: ExperienceCreateRequest,
    provider: CurrentProvider,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperienceDetail:
    experience = await experience_service.create_experience(session, provider, payload)
    return ExperienceDetail.model_validate(experience)


@router.get("/{experience_id}", response_model=ExperienceDetail)
async def get_experience(
    experience_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> ExperienceDetail:
    repository = ExperienceRepository(session)
    experience = await repository.get_by_id(experience_id)
    if experience is None:
        raise ApiError("Experience not found", status_code=404)

    detail = ExperienceDetail.model_validate(experience)

    review_repo = ReviewRepository(session)
    top_reviews, total_reviews = await review_repo.list_for_experience(
        experience_id, limit=5, sort="newest"
    )
    avg_rating, count, distribution = await review_repo.get_distribution_and_avg(experience_id)
    real_review_count = await review_repo.get_real_review_count(experience_id)

    detail.reviews = [ExperienceReviewSummary.model_validate(r) for r in top_reviews]
    detail.rating_summary = RatingSummary(
        average_rating=avg_rating,
        review_count=count,
        rating_distribution=distribution,
        is_synthetic=count > 0 and real_review_count == 0,
    )
    detail.availability_slots = [
        AvailabilitySlotSummary.model_validate(s) for s in experience.availability_slots
    ]

    return detail


@router.get("/{experience_id}/reviews", response_model=ExperienceReviewListResponse)
async def list_experience_reviews(
    experience_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[Literal["newest", "highest", "lowest"], Query()] = "newest",
) -> ExperienceReviewListResponse:
    repository = ExperienceRepository(session)
    experience = await repository.get_by_id(experience_id)
    if experience is None:
        raise ApiError("Experience not found", status_code=404)

    review_repo = ReviewRepository(session)
    reviews, total = await review_repo.list_for_experience(
        experience_id, limit=limit, offset=offset, sort=sort
    )
    items = [ExperienceReviewSummary.model_validate(r) for r in reviews]
    return ExperienceReviewListResponse(items=items, total=total, limit=limit, offset=offset)


async def _get_owned_or_404(session: AsyncSession, experience_id: str, provider: Provider) -> Experience:
    repository = ExperienceRepository(session)
    experience = await repository.get_owned_by_id(experience_id, provider.id)
    if experience is None:
        # Deliberately identical to "does not exist" — do not disclose
        # that the experience exists but belongs to another provider.
        raise ApiError("Experience not found", status_code=404)
    return experience


@router.patch("/{experience_id}", response_model=ExperienceDetail)
async def update_experience(
    experience_id: str,
    payload: ExperienceUpdateRequest,
    provider: CurrentProvider,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperienceDetail:
    experience = await _get_owned_or_404(session, experience_id, provider)
    updated = await experience_service.update_experience(session, experience, payload)
    return ExperienceDetail.model_validate(updated)


@router.delete("/{experience_id}", response_model=ExperienceDetail)
async def deactivate_experience(
    experience_id: str,
    provider: CurrentProvider,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperienceDetail:
    experience = await _get_owned_or_404(session, experience_id, provider)
    deactivated = await experience_service.deactivate_experience(session, experience)
    return ExperienceDetail.model_validate(deactivated)
