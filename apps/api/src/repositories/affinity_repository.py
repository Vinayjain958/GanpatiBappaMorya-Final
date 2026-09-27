from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.affinity import TravelerAffinity


class AffinityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_traveler_id(self, traveler_id: str) -> list[TravelerAffinity]:
        stmt = select(TravelerAffinity).where(TravelerAffinity.traveler_id == traveler_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_dimension(self, traveler_id: str, dimension_type: str) -> list[TravelerAffinity]:
        stmt = select(TravelerAffinity).where(
            TravelerAffinity.traveler_id == traveler_id,
            TravelerAffinity.dimension_type == dimension_type
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
        
    async def get_by_dimension_key(self, traveler_id: str, dimension_type: str, dimension_key: str) -> TravelerAffinity | None:
        stmt = select(TravelerAffinity).where(
            TravelerAffinity.traveler_id == traveler_id,
            TravelerAffinity.dimension_type == dimension_type,
            TravelerAffinity.dimension_key == dimension_key
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def upsert(
        self, 
        traveler_id: str, 
        dimension_type: str, 
        dimension_key: str, 
        updates: dict[str, Any]
    ) -> TravelerAffinity:
        affinity = await self.get_by_dimension_key(traveler_id, dimension_type, dimension_key)
        if not affinity:
            affinity = TravelerAffinity(
                traveler_id=traveler_id,
                dimension_type=dimension_type,
                dimension_key=dimension_key
            )
            self.session.add(affinity)
            
        for key, value in updates.items():
            if hasattr(affinity, key) and key not in ("id", "traveler_id", "dimension_type", "dimension_key"):
                setattr(affinity, key, value)
                
        await self.session.flush()
        return affinity
        
    async def bulk_get(self, traveler_id: str, pairs: list[tuple[str, str]]) -> dict[tuple[str, str], TravelerAffinity]:
        if not pairs:
            return {}
            
        stmt = select(TravelerAffinity).where(TravelerAffinity.traveler_id == traveler_id)
        result = await self.session.execute(stmt)
        all_affinities = result.scalars().all()
        
        pair_set = set(pairs)
        return {
            (aff.dimension_type, aff.dimension_key): aff 
            for aff in all_affinities 
            if (aff.dimension_type, aff.dimension_key) in pair_set
        }
