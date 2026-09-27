from __future__ import annotations

from datetime import date, time
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CollabGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_groups"
    __table_args__ = (UniqueConstraint("invite_code", name="uq_collab_groups_invite_code"),)

    owner_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    destination: Mapped[str | None] = mapped_column(String(120), nullable=True)
    itinerary_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    origin_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    travel_mode: Mapped[str] = mapped_column(String(20), default="walking", nullable=False)
    invite_code: Mapped[str] = mapped_column(String(48), nullable=False)
    objectives: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class CollabMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_collab_member_group_user"),)

    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class CollabMemberPreferences(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_member_preferences"
    __table_args__ = (UniqueConstraint("member_id", name="uq_collab_member_preferences_member"),)

    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    soft_preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    hard_constraints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CollabWishlistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_wishlist_items"
    __table_args__ = (
        UniqueConstraint("group_id", "experience_id", name="uq_collab_wishlist_group_experience"),
    )

    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experience_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_by_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("collab_members.id", ondelete="SET NULL"), nullable=True
    )


class CollabWishlistReaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_wishlist_reactions"
    __table_args__ = (
        UniqueConstraint("wishlist_item_id", "member_id", name="uq_collab_reaction_item_member"),
    )

    wishlist_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_wishlist_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reaction: Mapped[str] = mapped_column(String(16), nullable=False)


class CollabDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_decisions"

    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_members.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)


class CollabDecisionOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_decision_options"

    decision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experience_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="CASCADE"), nullable=True, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)


class CollabVote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_votes"
    __table_args__ = (UniqueConstraint("decision_id", "member_id", name="uq_collab_vote_decision_member"),)

    decision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_decision_options.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_members.id", ondelete="CASCADE"), nullable=False, index=True
    )


class CollabItinerary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_itineraries"
    __table_args__ = (UniqueConstraint("group_id", name="uq_collab_itinerary_group"),)

    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_members.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class CollabItineraryItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_itinerary_items"
    __table_args__ = (
        UniqueConstraint("itinerary_id", "sequence_order", name="uq_collab_itinerary_item_order"),
    )

    itinerary_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_itineraries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experience_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CollabItineraryApproval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_itinerary_approvals"
    __table_args__ = (
        UniqueConstraint("itinerary_id", "member_id", name="uq_collab_itinerary_approval_member"),
    )

    itinerary_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_itineraries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class CollabItineraryTrip(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collab_itinerary_trips"
    __table_args__ = (
        UniqueConstraint("collab_itinerary_id", "user_id", name="uq_collab_itinerary_trip_user"),
    )

    collab_itinerary_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collab_itineraries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    itinerary_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("itineraries.id", ondelete="CASCADE"), nullable=False, index=True
    )


__all__ = [
    "CollabDecision", "CollabDecisionOption", "CollabGroup", "CollabItinerary",
    "CollabItineraryApproval", "CollabItineraryItem", "CollabItineraryTrip", "CollabMember",
    "CollabMemberPreferences", "CollabVote", "CollabWishlistItem", "CollabWishlistReaction",
]
