from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.provider import Provider


class ProviderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, provider_id: str) -> Provider | None:
        query = select(Provider).where(Provider.id == provider_id)
        result = await self._session.execute(query)
        return result.scalars().one_or_none()

    async def get_by_user_id(self, user_id: str) -> Provider | None:
        query = select(Provider).where(Provider.user_id == user_id)
        result = await self._session.execute(query)
        return result.scalars().one_or_none()

    def add(self, provider: Provider) -> None:
        self._session.add(provider)
