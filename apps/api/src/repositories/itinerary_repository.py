from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.itinerary import Itinerary


class ItineraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self) -> Select[tuple[Itinerary]]:
        return select(Itinerary).options(
            selectinload(Itinerary.items),
            selectinload(Itinerary.custom_activities),
        )

    def add(self, itinerary: Itinerary) -> None:
        self._session.add(itinerary)

    async def get_by_id(self, itinerary_id: str) -> Itinerary | None:
        query = self._base_query().where(Itinerary.id == itinerary_id)
        result = await self._session.execute(query)
        return result.scalars().unique().one_or_none()

    async def get_owned_by_id(self, itinerary_id: str, traveler_id: str) -> Itinerary | None:
        query = self._base_query().where(
            Itinerary.id == itinerary_id, Itinerary.traveler_id == traveler_id
        )
        result = await self._session.execute(query)
        return result.scalars().unique().one_or_none()

    async def list_by_traveler(
        self, traveler_id: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[Itinerary], int]:
        query = (
            self._base_query()
            .where(Itinerary.traveler_id == traveler_id)
            .order_by(Itinerary.itinerary_date.desc(), Itinerary.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_query = select(func.count(Itinerary.id)).where(Itinerary.traveler_id == traveler_id)
        total = (await self._session.execute(count_query)).scalar_one()
        rows = (await self._session.execute(query)).scalars().unique().all()
        return list(rows), total


__all__ = ["ItineraryRepository"]
