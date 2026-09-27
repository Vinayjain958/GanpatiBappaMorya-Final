from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.location import Location


class LocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, location_id: str) -> Location | None:
        query = select(Location).where(Location.id == location_id)
        result = await self._session.execute(query)
        return result.scalars().one_or_none()
