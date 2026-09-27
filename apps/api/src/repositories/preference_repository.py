from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.preference import TravelerPreference


class PreferenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_traveler_id(self, traveler_id: str) -> TravelerPreference | None:
        stmt = select(TravelerPreference).where(TravelerPreference.traveler_id == traveler_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def upsert(self, traveler_id: str, data: dict[str, Any]) -> TravelerPreference:
        preference = await self.get_by_traveler_id(traveler_id)
        if not preference:
            preference = TravelerPreference(traveler_id=traveler_id)
            self.session.add(preference)
            
        for key, value in data.items():
            if hasattr(preference, key) and key != "id" and key != "traveler_id":
                setattr(preference, key, value)
                
        await self.session.flush()
        return preference
