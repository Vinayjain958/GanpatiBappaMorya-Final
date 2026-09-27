from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import CurrentProvider
from src.core.errors import ApiError
from src.models.availability import ExperienceAvailability
from src.models.experience import Experience
from src.repositories.availability_repository import AvailabilityRepository
from src.repositories.experience_repository import ExperienceRepository
from src.schemas.availability import (
    AvailabilityCreateRequest,
    AvailabilityResponse,
    AvailabilityUpdateRequest,
)

router = APIRouter(prefix="/experiences/{experience_id}/availability", tags=["availability"])


async def _get_owned_experience_or_404(
    session: AsyncSession, experience_id: str, provider_id: str
) -> Experience:
    experience = await ExperienceRepository(session).get_owned_by_id(experience_id, provider_id)
    if experience is None:
        raise ApiError("Experience not found", status_code=404)
    return experience


@router.get("", response_model=list[AvailabilityResponse])
async def list_availability(
    experience_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> list[AvailabilityResponse]:
    # Public read: an experience must exist to have availability listed,
    # but ownership is not required to view it.
    experience = await ExperienceRepository(session).get_by_id(experience_id)
    if experience is None:
        raise ApiError("Experience not found", status_code=404)
    rows = await AvailabilityRepository(session).list_for_experience(experience_id)
    return [AvailabilityResponse.model_validate(row) for row in rows]


@router.post("", response_model=AvailabilityResponse, status_code=201)
async def create_availability(
    experience_id: str,
    payload: AvailabilityCreateRequest,
    provider: CurrentProvider,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AvailabilityResponse:
    await _get_owned_experience_or_404(session, experience_id, provider.id)

    availability = ExperienceAvailability(
        experience_id=experience_id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        capacity=payload.capacity,
        available_slots=payload.available_slots if payload.available_slots is not None else payload.capacity,
        status="active",
    )
    AvailabilityRepository(session).add(availability)
    await session.commit()
    await session.refresh(availability)
    return AvailabilityResponse.model_validate(availability)


@router.patch("/{availability_id}", response_model=AvailabilityResponse)
async def update_availability(
    experience_id: str,
    availability_id: str,
    payload: AvailabilityUpdateRequest,
    provider: CurrentProvider,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AvailabilityResponse:
    await _get_owned_experience_or_404(session, experience_id, provider.id)

    repository = AvailabilityRepository(session)
    availability = await repository.get_for_experience(availability_id, experience_id)
    if availability is None:
        raise ApiError("Availability slot not found", status_code=404)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(availability, field, value)

    if availability.starts_at >= availability.ends_at:
        raise ApiError("starts_at must be before ends_at", status_code=422)

    await session.commit()
    await session.refresh(availability)
    return AvailabilityResponse.model_validate(availability)


@router.delete("/{availability_id}", response_model=AvailabilityResponse)
async def deactivate_availability(
    experience_id: str,
    availability_id: str,
    provider: CurrentProvider,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AvailabilityResponse:
    await _get_owned_experience_or_404(session, experience_id, provider.id)

    repository = AvailabilityRepository(session)
    availability = await repository.get_for_experience(availability_id, experience_id)
    if availability is None:
        raise ApiError("Availability slot not found", status_code=404)

    availability.status = "inactive"
    await session.commit()
    await session.refresh(availability)
    return AvailabilityResponse.model_validate(availability)
