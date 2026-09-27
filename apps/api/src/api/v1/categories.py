from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.repositories.category_repository import CategoryRepository
from src.schemas.category import CategoryResponse

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/available", response_model=list[CategoryResponse])
async def list_available_categories(
    session: Annotated[AsyncSession, Depends(get_session)],
    city: Annotated[str | None, Query(max_length=120)] = None,
    locality: Annotated[str | None, Query(max_length=120)] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[float | None, Query(gt=0, le=200)] = None,
) -> list[CategoryResponse]:
    if (lat is None) != (lng is None):
        raise HTTPException(status_code=422, detail="lat and lng must be provided together")
    if radius_km is not None and lat is None:
        raise HTTPException(status_code=422, detail="radius_km requires lat and lng")
    rows = await CategoryRepository(session).list_available(
        city=city, locality=locality, lat=lat, lng=lng, radius_km=radius_km
    )
    return [CategoryResponse.model_validate(row) for row in rows]


@router.get("", response_model=list[CategoryResponse])
async def list_categories(session: Annotated[AsyncSession, Depends(get_session)]) -> list[CategoryResponse]:
    rows = await CategoryRepository(session).list()
    return [CategoryResponse.model_validate(row) for row in rows]
