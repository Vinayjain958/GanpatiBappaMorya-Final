from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.itinerary_item import ItineraryItem


class ItineraryItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, item: ItineraryItem) -> None:
        self._session.add(item)

    async def get_by_id(self, item_id: str) -> ItineraryItem | None:
        result = await self._session.execute(select(ItineraryItem).where(ItineraryItem.id == item_id))
        return result.scalars().one_or_none()

    async def list_by_itinerary(self, itinerary_id: str) -> list[ItineraryItem]:
        query = (
            select(ItineraryItem)
            .where(ItineraryItem.itinerary_id == itinerary_id)
            .order_by(ItineraryItem.sequence_order)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())


__all__ = ["ItineraryItemRepository"]
