from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.affinity import TravelerAffinity
    from src.models.interaction import TravelerInteraction
    from src.models.preference import TravelerPreference
    from src.models.user import User


class Traveler(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Traveler profile. One-to-one with User. Preference/affinity modeling
    used for ranking arrives in Phase 7 — these fields are freeform for now."""

    __tablename__ = "travelers"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    traveler_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    accessibility_requirements: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    user: Mapped[User] = relationship(back_populates="traveler")
    preference: Mapped[TravelerPreference | None] = relationship(back_populates="traveler", uselist=False, cascade="all, delete-orphan")
    affinities: Mapped[list[TravelerAffinity]] = relationship(back_populates="traveler", cascade="all, delete-orphan")
    interactions: Mapped[list[TravelerInteraction]] = relationship(back_populates="traveler", cascade="all, delete-orphan")
