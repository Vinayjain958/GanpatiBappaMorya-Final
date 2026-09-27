from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self) -> Select[tuple[User]]:
        return select(User).options(selectinload(User.traveler))

    async def get_by_email(self, email: str) -> User | None:
        query = self._base_query().where(User.email == email.strip().lower())
        result = await self._session.execute(query)
        return result.scalars().one_or_none()

    async def get_by_id(self, user_id: str) -> User | None:
        query = self._base_query().where(User.id == user_id)
        result = await self._session.execute(query)
        return result.scalars().one_or_none()

    def add(self, user: User) -> None:
        self._session.add(user)
