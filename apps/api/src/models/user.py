from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.traveler import Traveler

UserRole = Enum("traveler", "provider", "admin", name="user_role", native_enum=False)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Core account entity. Authentication (password verification, JWT) is
    implemented in Phase 3 — password_hash is nullable until then."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(UserRole, default="traveler", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    traveler: Mapped[Traveler | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
