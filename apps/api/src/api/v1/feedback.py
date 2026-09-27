from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.db import get_session
from src.core.deps import require_traveler
from src.core.errors import ApiError
from src.models.user import User
from src.repositories.experience_repository import ExperienceRepository
from src.repositories.interaction_repository import InteractionRepository
from src.schemas.feedback import (
    AffinityProfileResponse,
    RecordInteractionRequest,
    RecordInteractionResponse,
    TravelerAffinitySummary,
)
from src.services.affinity import TravelerAffinityService
from src.services.metrics import RecommendationMetricsService
from src.services.provider_intelligence.notifications import ProviderNotificationService

router = APIRouter(prefix="/feedback", tags=["feedback"])

@router.post("/interactions", response_model=RecordInteractionResponse)
async def record_interaction(
    payload: RecordInteractionRequest,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RecordInteractionResponse:
    traveler_id = user.traveler.id
    
    # Verify experience exists
    repo = ExperienceRepository(session)
    experience = await repo.get_by_id(payload.experience_id)
    if not experience:
        raise ApiError("Experience not found", status_code=404)
        
    inter_repo = InteractionRepository(session)
    
    # Check for idempotency
    existing = await inter_repo.get_by_client_event_id(traveler_id, payload.client_event_id)
    if existing:
        return RecordInteractionResponse(
            interaction_id=existing.id,
            created=False,
            idempotent=True
        )
        
    # Create Interaction
    interaction = await inter_repo.create(
        traveler_id=traveler_id,
        experience_id=payload.experience_id,
        event_type=payload.event_type,
        client_event_id=payload.client_event_id,
        rating=payload.rating,
        rank_position=payload.rank_position,
        recommendation_session_id=payload.recommendation_session_id,
        source=payload.source,
    )
    
    # Update Affinities
    affinity_service = TravelerAffinityService(session, settings)
    await affinity_service.update_from_interaction(interaction, experience)
    
    # Phase 10: behavioral match notification
    notification_svc = ProviderNotificationService(session, settings)
    await notification_svc.maybe_notify_provider(interaction, experience)
    
    await session.commit()
    
    return RecordInteractionResponse(
        interaction_id=interaction.id,
        created=True,
        idempotent=False
    )

@router.get("/profile/affinities", response_model=AffinityProfileResponse)
async def get_affinities(
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AffinityProfileResponse:
    traveler_id = user.traveler.id
    
    affinity_service = TravelerAffinityService(session, settings)
    affinities = await affinity_service.get_affinities(traveler_id)
    
    summaries = [
        TravelerAffinitySummary.model_validate(aff)
        for aff in affinities
    ]
    
    return AffinityProfileResponse(
        traveler_id=traveler_id,
        affinities=summaries,
        personalized_since=None
    )

@router.get("/metrics", response_model=dict[str, object])
async def get_metrics(
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    traveler_id = user.traveler.id
    
    metrics_service = RecommendationMetricsService(session)
    return await metrics_service.compute_metrics(traveler_id)
