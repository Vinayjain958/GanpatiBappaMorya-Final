"""Feasibility check endpoint (Phase 6).

Deterministic only — no LLM call on this path. Requires authentication
like every other discovery-adjacent endpoint (matches Phase 4/5
convention); never accepts an authoritative user_id from the body.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.routing import RoutingAdapter
from src.core.config import Settings, get_settings
from src.core.db import get_session
from src.core.deps import CurrentUser
from src.core.errors import ApiError
from src.core.location import get_routing_adapter
from src.repositories.experience_repository import ExperienceRepository
from src.schemas.feasibility import FeasibilityCheckRequest, FeasibilityVerdict
from src.services.feasibility import FeasibilityService

router = APIRouter(prefix="/feasibility", tags=["feasibility"])


@router.post("/check", response_model=FeasibilityVerdict)
async def check_feasibility(
    payload: FeasibilityCheckRequest,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
) -> FeasibilityVerdict:
    experience = await ExperienceRepository(session).get_by_id(payload.experience_id)
    if experience is None:
        raise ApiError("Experience not found", status_code=404)

    service = FeasibilityService(routing)
    return await service.evaluate(experience, payload.constraints, travel_profile=settings.osrm_profile)


__all__ = ["router"]
