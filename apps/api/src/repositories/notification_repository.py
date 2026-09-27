from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.provider_notification import ProviderNotification


class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_provider(
        self, provider_id: str, unread_only: bool = False, limit: int = 50, offset: int = 0
    ) -> tuple[list[ProviderNotification], int]:
        
        base_stmt = select(ProviderNotification).where(ProviderNotification.provider_id == provider_id)
        if unread_only:
            base_stmt = base_stmt.where(ProviderNotification.is_read == False)
            
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()
        
        stmt = base_stmt.order_by(ProviderNotification.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        
        return items, total

    async def get_by_id_and_provider(self, notification_id: str, provider_id: str) -> ProviderNotification | None:
        stmt = select(ProviderNotification).where(
            ProviderNotification.id == notification_id,
            ProviderNotification.provider_id == provider_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_read(self, notification: ProviderNotification) -> None:
        notification.is_read = True
        self.session.add(notification)

    async def get_unread_count(self, provider_id: str) -> int:
        stmt = select(func.count()).select_from(ProviderNotification).where(
            ProviderNotification.provider_id == provider_id,
            ProviderNotification.is_read == False
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_cooldown_key(self, provider_id: str, cooldown_key: str, since: datetime) -> ProviderNotification | None:
        stmt = select(ProviderNotification).where(
            ProviderNotification.provider_id == provider_id,
            ProviderNotification.cooldown_key == cooldown_key,
            ProviderNotification.created_at >= since
        ).order_by(ProviderNotification.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, notification: ProviderNotification) -> ProviderNotification:
        self.session.add(notification)
        return notification
