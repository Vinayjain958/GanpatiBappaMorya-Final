from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.availability import ExperienceAvailability


class AvailabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_experience(self, experience_id: str) -> list[ExperienceAvailability]:
        query = (
            select(ExperienceAvailability)
            .where(ExperienceAvailability.experience_id == experience_id)
            .order_by(ExperienceAvailability.starts_at)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_for_experience(
        self, availability_id: str, experience_id: str
    ) -> ExperienceAvailability | None:
        query = select(ExperienceAvailability).where(
            ExperienceAvailability.id == availability_id,
            ExperienceAvailability.experience_id == experience_id,
        )
        result = await self._session.execute(query)
        return result.scalars().one_or_none()

    def add(self, availability: ExperienceAvailability) -> None:
        self._session.add(availability)
