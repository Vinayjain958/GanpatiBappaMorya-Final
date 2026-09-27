from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import ApiError
from src.models.collab import CollabGroup, CollabMember, CollabMemberPreferences
from src.models.preference import TravelerPreference
from src.models.user import User
from src.schemas.collab import CollabGroupCreate, CollabGroupResponse, CollabMemberResponse


async def require_group_member(
    session: AsyncSession, group_id: str, user_id: str
) -> tuple[CollabGroup, CollabMember]:
    result = await session.execute(
        select(CollabGroup, CollabMember)
        .join(CollabMember, CollabMember.group_id == CollabGroup.id)
        .where(
            CollabGroup.id == group_id,
            CollabGroup.status == "ACTIVE",
            CollabMember.user_id == user_id,
            CollabMember.status == "ACTIVE",
        )
    )
    row = result.one_or_none()
    if row is None:
        raise ApiError("Collab group not found", status_code=404)
    return row[0], row[1]


def require_group_owner(member: CollabMember) -> None:
    if member.role != "owner":
        raise ApiError("Only the group owner can perform this action", status_code=403)


async def _member_preferences_with_existing_snapshot(
    session: AsyncSession, member_id: str, user: User
) -> CollabMemberPreferences:
    """Copy only established traveler preference fields into this group's
    independent profile. Later Collab edits never write back to the source."""
    traveler = user.traveler
    preference = None
    if traveler is not None:
        preference = await session.scalar(
            select(TravelerPreference).where(TravelerPreference.traveler_id == traveler.id)
        )

    soft: dict[str, Any] = {}
    hard: dict[str, Any] = {}
    if preference is not None:
        if preference.preferred_category_slugs:
            soft["category_slugs"] = list(dict.fromkeys(preference.preferred_category_slugs))
        if preference.budget_sensitivity:
            soft["budget_sensitivity"] = preference.budget_sensitivity
        if preference.preferred_duration_minutes is not None:
            soft["preferred_duration_minutes"] = preference.preferred_duration_minutes
        if preference.preferred_max_distance_km is not None and preference.preferred_max_distance_km > 0:
            hard["max_distance_km"] = preference.preferred_max_distance_km
        existing_accessibility = preference.accessibility_requirements or []
        supported_accessibility = [
            value for value in existing_accessibility if value in {"wheelchair_accessible", "step_free"}
        ]
        if supported_accessibility:
            hard["accessibility_requirements"] = list(dict.fromkeys(supported_accessibility))

    return CollabMemberPreferences(
        member_id=member_id,
        soft_preferences=soft,
        hard_constraints=hard,
    )


async def create_group(
    session: AsyncSession, user: User, payload: CollabGroupCreate
) -> tuple[CollabGroup, CollabMember]:
    group = CollabGroup(
        owner_user_id=user.id,
        title=payload.title.strip(),
        destination=payload.destination,
        itinerary_date=payload.itinerary_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        origin_latitude=payload.origin_latitude,
        origin_longitude=payload.origin_longitude,
        travel_mode=payload.travel_mode,
        invite_code=secrets.token_urlsafe(18),
        objectives=payload.objectives,
    )
    session.add(group)
    await session.flush()
    member = CollabMember(group_id=group.id, user_id=user.id, role="owner")
    session.add(member)
    await session.flush()
    session.add(await _member_preferences_with_existing_snapshot(session, member.id, user))
    await session.commit()
    await session.refresh(group)
    return group, member


async def join_group(
    session: AsyncSession, user: User, invite_code: str
) -> tuple[CollabGroup, CollabMember]:
    group = await session.scalar(
        select(CollabGroup).where(
            CollabGroup.invite_code == invite_code.strip(), CollabGroup.status == "ACTIVE"
        )
    )
    if group is None:
        raise ApiError("Invite code is invalid or the group is closed", status_code=404)

    member = await session.scalar(
        select(CollabMember).where(
            CollabMember.group_id == group.id,
            CollabMember.user_id == user.id,
        )
    )
    if member is None:
        member = CollabMember(group_id=group.id, user_id=user.id, role="member")
        session.add(member)
        await session.flush()
        session.add(await _member_preferences_with_existing_snapshot(session, member.id, user))
        await session.commit()
        await session.refresh(member)
    elif member.status != "ACTIVE":
        member.status = "ACTIVE"
        member.role = "member"
        await session.commit()
        await session.refresh(member)
    return group, member


async def list_groups(session: AsyncSession, user_id: str) -> list[CollabGroup]:
    result = await session.scalars(
        select(CollabGroup)
        .join(CollabMember, CollabMember.group_id == CollabGroup.id)
        .where(
            CollabMember.user_id == user_id,
            CollabMember.status == "ACTIVE",
            CollabGroup.status == "ACTIVE",
        )
        .order_by(CollabGroup.updated_at.desc())
    )
    return list(result.all())


async def group_response(
    session: AsyncSession,
    group: CollabGroup,
    my_member: CollabMember,
) -> CollabGroupResponse:
    rows = await session.execute(
        select(CollabMember, User, CollabMemberPreferences)
        .join(User, User.id == CollabMember.user_id)
        .outerjoin(CollabMemberPreferences, CollabMemberPreferences.member_id == CollabMember.id)
        .where(CollabMember.group_id == group.id, CollabMember.status == "ACTIVE")
        .order_by(CollabMember.created_at)
    )
    members: list[CollabMemberResponse] = []
    for member, user, preferences in rows.all():
        members.append(
            CollabMemberResponse(
                id=member.id,
                user_id=user.id,
                email=user.email,
                role=member.role,
                soft_preferences=(preferences.soft_preferences if preferences else {}) or {},
                hard_constraints=(preferences.hard_constraints if preferences else {}) or {},
            )
        )
    return CollabGroupResponse(
        id=group.id,
        owner_user_id=group.owner_user_id,
        title=group.title,
        destination=group.destination,
        itinerary_date=group.itinerary_date,
        start_time=group.start_time,
        end_time=group.end_time,
        origin_latitude=group.origin_latitude,
        origin_longitude=group.origin_longitude,
        travel_mode=group.travel_mode,
        invite_code=group.invite_code,
        objectives=group.objectives or {},
        status=group.status,
        my_member_id=my_member.id,
        members=members,
    )


def profile_payload(member: CollabMember, soft: dict[str, Any] | None, hard: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "id": member.id,
        "soft_preferences": soft or {},
        "hard_constraints": hard or {},
    }


__all__ = [
    "create_group", "group_response", "join_group", "list_groups", "profile_payload",
    "require_group_member", "require_group_owner",
]
