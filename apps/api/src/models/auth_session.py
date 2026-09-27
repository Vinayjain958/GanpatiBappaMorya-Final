from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.user import User


class AuthSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single issued refresh token, tracked for rotation and revocation.

    The raw refresh token is never stored — only a SHA-256 hash
    (`token_hash`), so a database read alone cannot be used to forge a
    session. `jti` is the JWT ID embedded in the refresh token itself,
    used to look up the session without needing the raw token.

    Rotation: on every successful /auth/refresh, this row is marked
    revoked and `replaced_by_session_id` points at the new row. Reuse of
    an already-rotated/revoked refresh token is rejected outright
    (docs/DECISIONS.md ADR-020) rather than silently issuing a new session.
    """

    __tablename__ = "auth_sessions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("auth_sessions.id", ondelete="SET NULL"), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)

    user: Mapped[User] = relationship()
