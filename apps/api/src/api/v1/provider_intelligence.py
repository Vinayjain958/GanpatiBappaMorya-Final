from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.db import get_session
from src.core.deps import CurrentProvider, get_current_provider
from src.schemas.provider_intelligence import (
    ProviderInsightResponse,
    ProviderNotificationListResponse,
    ProviderNotificationResponse,
)
from src.services.provider_intelligence.provider_insights import ProviderInsightService
from src.repositories.notification_repository import NotificationRepository

router = APIRouter(prefix="/provider", tags=["provider_intelligence"])


@router.get("/insights", response_model=ProviderInsightResponse)
async def get_provider_insights(
    provider: Annotated[CurrentProvider, Depends(get_current_provider)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    window: str = "30d",
    granularity: str = "auto",
) -> ProviderInsightResponse:
    service = ProviderInsightService(session, settings)
    return await service.get_insights(provider.id, window, granularity, include_synthetic=True)


@router.get("/notifications", response_model=ProviderNotificationListResponse)
async def get_notifications(
    provider: Annotated[CurrentProvider, Depends(get_current_provider)],
    session: Annotated[AsyncSession, Depends(get_session)],
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> ProviderNotificationListResponse:
    repo = NotificationRepository(session)
    items, total = await repo.list_by_provider(provider.id, unread_only, limit, offset)
    unread_count = await repo.get_unread_count(provider.id)
    
    response_items = [ProviderNotificationResponse.model_validate(i) for i in items]
    return ProviderNotificationListResponse(items=response_items, total=total, unread_count=unread_count)


@router.post("/notifications/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: str,
    provider: Annotated[CurrentProvider, Depends(get_current_provider)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    repo = NotificationRepository(session)
    notif = await repo.get_by_id_and_provider(notification_id, provider.id)
    if notif:
        await repo.mark_read(notif)
        await session.commit()
