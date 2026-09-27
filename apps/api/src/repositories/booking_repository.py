from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.booking_request import BookingRequest


class BookingRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, booking: BookingRequest) -> None:
        self._session.add(booking)

    async def get_by_id(self, booking_id: str) -> BookingRequest | None:
        result = await self._session.execute(select(BookingRequest).where(BookingRequest.id == booking_id))
        return result.scalars().one_or_none()

    async def get_owned_by_traveler(self, booking_id: str, traveler_id: str) -> BookingRequest | None:
        query = select(BookingRequest).where(
            BookingRequest.id == booking_id, BookingRequest.traveler_id == traveler_id
        )
        result = await self._session.execute(query)
        return result.scalars().one_or_none()

    async def get_owned_by_provider(self, booking_id: str, provider_id: str) -> BookingRequest | None:
        query = select(BookingRequest).where(
            BookingRequest.id == booking_id, BookingRequest.provider_id == provider_id
        )
        result = await self._session.execute(query)
        return result.scalars().one_or_none()

    async def list_by_traveler(
        self, traveler_id: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[BookingRequest], int]:
        query = (
            select(BookingRequest)
            .where(BookingRequest.traveler_id == traveler_id)
            .order_by(BookingRequest.requested_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_query = select(func.count(BookingRequest.id)).where(BookingRequest.traveler_id == traveler_id)
        total = (await self._session.execute(count_query)).scalar_one()
        rows = (await self._session.execute(query)).scalars().all()
        return list(rows), total

    async def list_by_provider(
        self, provider_id: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[BookingRequest], int]:
        query = (
            select(BookingRequest)
            .where(BookingRequest.provider_id == provider_id)
            .order_by(BookingRequest.requested_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_query = select(func.count(BookingRequest.id)).where(BookingRequest.provider_id == provider_id)
        total = (await self._session.execute(count_query)).scalar_one()
        rows = (await self._session.execute(query)).scalars().all()
        return list(rows), total


__all__ = ["BookingRequestRepository"]
