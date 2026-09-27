"""Provider-owned experience create/update orchestration.

`provider_id` is always taken from the authenticated `Provider` passed in
by the route (never from the request body) — see
src/schemas/experience_write.py and docs/DECISIONS.md ADR-021.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import ApiError
from src.models.experience import Experience
from src.models.location import Location
from src.models.opening_hour import ExperienceOpeningHour
from src.models.provider import Provider
from src.repositories.category_repository import CategoryRepository
from src.repositories.experience_repository import ExperienceRepository
from src.schemas.experience_write import ExperienceCreateRequest, ExperienceUpdateRequest

# Fields a provider may never set directly on their own experience —
# provenance/ownership stay server-controlled at all times.
_PROTECTED_FIELDS = {
    "provider_id",
    "source_type",
    "source_name",
    "source_record_id",
    "source_version",
    "source_license",
    "is_synthetic",
    "is_enriched",
    "created_at",
    "updated_at",
    "id",
}


async def create_experience(
    session: AsyncSession, provider: Provider, payload: ExperienceCreateRequest
) -> Experience:
    category = await CategoryRepository(session).get_by_id(payload.category_id)
    if category is None:
        raise ApiError("Invalid category_id", status_code=422)

    location = Location(
        latitude=payload.location.latitude,
        longitude=payload.location.longitude,
        place_name=payload.location.place_name,
        address=payload.location.address,
        locality=payload.location.locality,
        city=payload.location.city,
        state=payload.location.state,
        country=payload.location.country,
        postal_code=payload.location.postal_code,
        source_type="provider_submitted",
        is_synthetic=False,
        is_enriched=False,
    )
    session.add(location)
    await session.flush()

    experience = Experience(
        provider_id=provider.id,
        category_id=category.id,
        location_id=location.id,
        title=payload.title,
        short_description=payload.short_description,
        full_description=payload.full_description,
        currency=payload.currency,
        price=payload.price,
        minimum_price=payload.minimum_price,
        maximum_price=payload.maximum_price,
        price_type=payload.price_type,
        price_source="provider_submitted",
        is_price_estimated=False,
        duration_minutes=payload.duration_minutes,
        duration_is_estimated=False,
        minimum_group_size=payload.minimum_group_size,
        maximum_group_size=payload.maximum_group_size,
        capacity=payload.capacity,
        status=payload.status,
        verification_status="unverified",
        wheelchair_accessible=payload.wheelchair_accessible,
        step_free=payload.step_free,
        accessibility_notes=payload.accessibility_notes,
        suitability=payload.suitability,
        tags=payload.tags,
        opening_hours_status="structured" if payload.opening_hours else "unavailable",
        source_type="provider_submitted",
        is_synthetic=False,
        is_enriched=False,
    )
    session.add(experience)
    await session.flush()

    for window in payload.opening_hours:
        session.add(
            ExperienceOpeningHour(
                experience_id=experience.id,
                day_of_week=window.day_of_week,
                open_time=window.open_time,
                close_time=window.close_time,
                is_closed=window.is_closed,
            )
        )

    await session.commit()

    reloaded = await ExperienceRepository(session).get_by_id(experience.id)
    assert reloaded is not None
    return reloaded


async def update_experience(
    session: AsyncSession, experience: Experience, payload: ExperienceUpdateRequest
) -> Experience:
    updates = payload.model_dump(exclude_unset=True, exclude={"opening_hours"})

    if "category_id" in updates:
        category = await CategoryRepository(session).get_by_id(updates["category_id"])
        if category is None:
            raise ApiError("Invalid category_id", status_code=422)

    for field, value in updates.items():
        if field in _PROTECTED_FIELDS:
            continue
        setattr(experience, field, value)

    if payload.opening_hours is not None:
        for existing_window in list(experience.opening_hours):
            await session.delete(existing_window)
        await session.flush()
        for new_window in payload.opening_hours:
            session.add(
                ExperienceOpeningHour(
                    experience_id=experience.id,
                    day_of_week=new_window.day_of_week,
                    open_time=new_window.open_time,
                    close_time=new_window.close_time,
                    is_closed=new_window.is_closed,
                )
            )
        experience.opening_hours_status = "structured" if payload.opening_hours else "unavailable"

    await session.commit()

    reloaded = await ExperienceRepository(session).get_by_id(experience.id)
    assert reloaded is not None
    return reloaded


async def deactivate_experience(session: AsyncSession, experience: Experience) -> Experience:
    """Soft-delete: sets status to 'inactive' rather than deleting the
    row, per docs/DECISIONS.md ADR-021 — future phases may still need to
    reference this experience (interactions, itinerary items, etc.)."""
    experience.status = "inactive"
    await session.commit()
    await session.refresh(experience)
    return experience
