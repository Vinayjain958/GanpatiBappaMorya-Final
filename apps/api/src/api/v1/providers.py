from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.catalog_cache import invalidate_catalog_cache
from src.core.db import get_session
from src.core.deps import CurrentProvider
from src.repositories.experience_repository import ExperienceRepository
from src.schemas.experience import ExperienceListResponse, ExperienceSummary
from src.schemas.provider import ProviderMeResponse, ProviderUpdateRequest

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/me", response_model=ProviderMeResponse)
async def get_my_provider_profile(provider: CurrentProvider) -> ProviderMeResponse:
    return ProviderMeResponse.model_validate(provider)


@router.put("/me", response_model=ProviderMeResponse)
async def update_my_provider_profile(
    payload: ProviderUpdateRequest,
    provider: CurrentProvider,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProviderMeResponse:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(provider, field, value)
    await session.commit()
    await session.refresh(provider)
    invalidate_catalog_cache()  # provider name/details appear on Discover cards
    return ProviderMeResponse.model_validate(provider)


@router.get("/me/experiences", response_model=ExperienceListResponse)
async def list_my_experiences(
    provider: CurrentProvider,
    session: Annotated[AsyncSession, Depends(get_session)],
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExperienceListResponse:
    repository = ExperienceRepository(session)
    rows, total = await repository.list_by_provider(
        provider.id, status=status, limit=limit, offset=offset
    )
    return ExperienceListResponse(
        items=[ExperienceSummary.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
