from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auth_session import AuthSession


class AuthSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_jti(self, jti: str) -> AuthSession | None:
        query = select(AuthSession).where(AuthSession.jti == jti)
        result = await self._session.execute(query)
        return result.scalars().one_or_none()

    def add(self, auth_session: AuthSession) -> None:
        self._session.add(auth_session)

    async def revoke(self, auth_session: AuthSession, *, replaced_by_id: str | None = None) -> None:
        auth_session.revoked_at = datetime.now(UTC)
        auth_session.replaced_by_session_id = replaced_by_id

    async def revoke_all_for_user(self, user_id: str) -> None:
        query = select(AuthSession).where(
            AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
        )
        result = await self._session.execute(query)
        now = datetime.now(UTC)
        for auth_session in result.scalars().all():
            auth_session.revoked_at = now

    @staticmethod
    def is_valid(auth_session: AuthSession) -> bool:
        if auth_session.revoked_at is not None:
            return False
        expires_at = auth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at > datetime.now(UTC)
