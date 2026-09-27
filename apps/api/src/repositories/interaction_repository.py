from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.interaction import TravelerInteraction


class InteractionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_client_event_id(self, traveler_id: str, client_event_id: str) -> TravelerInteraction | None:
        stmt = select(TravelerInteraction).where(
            TravelerInteraction.traveler_id == traveler_id,
            TravelerInteraction.client_event_id == client_event_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_recent_for_traveler(self, traveler_id: str, event_types: list[str], limit: int = 100) -> list[TravelerInteraction]:
        stmt = select(TravelerInteraction).where(
            TravelerInteraction.traveler_id == traveler_id,
            TravelerInteraction.event_type.in_(event_types)
        ).order_by(TravelerInteraction.created_at.desc()).limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        traveler_id: str,
        experience_id: str,
        event_type: str,
        client_event_id: str,
        **kwargs: object,
    ) -> TravelerInteraction:
        # Idempotency check first
        existing = await self.get_by_client_event_id(traveler_id, client_event_id)
        if existing:
            return existing
            
        interaction = TravelerInteraction(
            traveler_id=traveler_id,
            experience_id=experience_id,
            event_type=event_type,
            client_event_id=client_event_id,
            **kwargs,
        )
        self.session.add(interaction)
        await self.session.flush()
        return interaction

    async def get_saved_experience_ids(self, traveler_id: str) -> list[str]:
        """Current SAVE state derived from this traveler's append-only log."""
        query = (
            select(TravelerInteraction.experience_id, TravelerInteraction.event_type)
            .where(
                TravelerInteraction.traveler_id == traveler_id,
                TravelerInteraction.event_type.in__(("SAVE", "UNSAVE")),
            )
            .order_by(
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at).asc(),
                TravelerInteraction.created_at.asc(),
            )
        )
        result = await self.session.execute(query)
        latest_by_experience: dict[str, str] = {}
        for experience_id, event_type in result.all():
            latest_by_experience[experience_id] = event_type
        return [
            experience_id
            for experience_id, event_type in latest_by_experience.items()
            if event_type == "SAVE"
        ]
