from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.conversation_session import ConversationSession


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_owned_by_id(self, conversation_id: str, user_id: str) -> ConversationSession | None:
        query = (
            select(ConversationSession)
            .options(selectinload(ConversationSession.messages))
            .where(ConversationSession.id == conversation_id, ConversationSession.user_id == user_id)
        )
        result = await self._session.execute(query)
        return result.scalars().unique().one_or_none()
