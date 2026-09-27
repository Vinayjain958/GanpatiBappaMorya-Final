from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.ai import AIAdapter
from src.adapters.routing import RoutingAdapter
from src.core.ai import get_ai_adapter
from src.core.config import Settings, get_settings
from src.core.db import get_session
from src.core.deps import require_traveler
from src.core.errors import ApiError
from src.core.location import get_routing_adapter
from src.models.collab import (
    CollabDecision,
    CollabDecisionOption,
    CollabGroup,
    CollabItinerary,
    CollabItineraryApproval,
    CollabItineraryItem,
    CollabItineraryTrip,
    CollabMember,
    CollabMemberPreferences,
    CollabVote,
    CollabWishlistItem,
    CollabWishlistReaction,
)
from src.models.experience import Experience
from src.models.user import User
from src.repositories.experience_repository import ExperienceRepository
from src.schemas.collab import (
    CollabDecisionCreate,
    CollabGroupCreate,
    CollabGroupResponse,
    CollabGroupUpdate,
    CollabItineraryApprovalUpdate,
    CollabItineraryUpdate,
    CollabJoinRequest,
    CollabPreferencesUpdate,
    CollabReactionRequest,
    CollabRecommendationResponse,
    CollabVoteRequest,
    CollabWishlistAddRequest,
    PreferenceAnalysisResponse,
)
from src.schemas.experience import ExperienceSummary
from src.services.collab.groups import (
    create_group,
    group_response,
    join_group,
    list_groups,
    require_group_member,
    require_group_owner,
)
from src.services.collab.planner import finalize_collab_plan
from src.services.collab.recommendations import recommend_for_group
from src.services.collab_preferences import analyze_group_preferences
from src.services.sse import publish_collab_event, sse_collab_updates_stream

router = APIRouter(prefix="/collab", tags=["collab"])


async def _context(session: AsyncSession, group_id: str, user: User) -> tuple[CollabGroup, CollabMember]:
    return await require_group_member(session, group_id, user.id)


async def _active_members(session: AsyncSession, group_id: str) -> list[CollabMember]:
    result = await session.scalars(
        select(CollabMember).where(CollabMember.group_id == group_id, CollabMember.status == "ACTIVE")
    )
    return list(result.all())


async def _get_real_experience(session: AsyncSession, experience_id: str) -> Experience:
    experience = await ExperienceRepository(session).get_by_id(experience_id)
    if (
        experience is None
        or experience.status != "active"
        or experience.is_synthetic
        or experience.provider.is_synthetic
        or experience.location.is_synthetic
    ):
        raise ApiError("Experience not found in the real active catalog", status_code=404)
    return experience


async def _plan_for_group(session: AsyncSession, group_id: str) -> CollabItinerary | None:
    return await session.scalar(select(CollabItinerary).where(CollabItinerary.group_id == group_id))


async def _reset_plan_review(session: AsyncSession, group_id: str) -> None:
    plan = await _plan_for_group(session, group_id)
    if plan is not None and plan.status != "FINALIZED":
        plan.status = "DRAFT"
        plan.version += 1
        await session.execute(delete(CollabItineraryApproval).where(CollabItineraryApproval.itinerary_id == plan.id))


async def _serialize_wishlist_item(
    session: AsyncSession, item: CollabWishlistItem, current_member_id: str
) -> dict[str, Any]:
    experience = await _get_real_experience(session, item.experience_id)
    reaction_rows = await session.execute(
        select(CollabWishlistReaction, CollabMember, User)
        .join(CollabMember, CollabMember.id == CollabWishlistReaction.member_id)
        .join(User, User.id == CollabMember.user_id)
        .where(
            CollabWishlistReaction.wishlist_item_id == item.id,
            CollabMember.status == "ACTIVE",
        )
    )
    reactions = [
        {"member_id": member.id, "email": user.email, "reaction": reaction.reaction}
        for reaction, member, user in reaction_rows.all()
    ]
    return {
        "id": item.id,
        "experience": ExperienceSummary.model_validate(experience),
        "added_by_member_id": item.added_by_member_id,
        "reactions": reactions,
        "my_reaction": next((row["reaction"] for row in reactions if row["member_id"] == current_member_id), None),
    }


async def _serialize_decision(session: AsyncSession, decision: CollabDecision) -> dict[str, Any]:
    options = list(
        (await session.scalars(
            select(CollabDecisionOption).where(CollabDecisionOption.decision_id == decision.id)
        )).all()
    )
    votes = list(
        (
            await session.execute(
                select(CollabVote, CollabMember, User)
                .join(CollabMember, CollabMember.id == CollabVote.member_id)
                .join(User, User.id == CollabMember.user_id)
                .where(CollabVote.decision_id == decision.id, CollabMember.status == "ACTIVE")
            )
        ).all()
    )
    return {
        "id": decision.id,
        "title": decision.title,
        "status": decision.status,
        "options": [
            {
                "id": option.id,
                "label": option.label,
                "experience_id": option.experience_id,
                "vote_count": sum(vote.option_id == option.id for vote, _, _ in votes),
            }
            for option in options
        ],
        "votes": [
            {"member_id": member.id, "email": user.email, "option_id": vote.option_id}
            for vote, member, user in votes
        ],
    }


async def _serialize_plan(session: AsyncSession, plan: CollabItinerary | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    item_rows = await session.scalars(
        select(CollabItineraryItem)
        .where(CollabItineraryItem.itinerary_id == plan.id)
        .order_by(CollabItineraryItem.sequence_order)
    )
    item_payload: list[dict[str, Any]] = []
    for item in item_rows.all():
        experience = await _get_real_experience(session, item.experience_id)
        item_payload.append(
            {
                "id": item.id,
                "experience": ExperienceSummary.model_validate(experience),
                "experience_id": item.experience_id,
                "sequence_order": item.sequence_order,
                "is_optional": item.is_optional,
            }
        )
    approvals = await session.execute(
        select(CollabItineraryApproval, CollabMember, User)
        .join(CollabMember, CollabMember.id == CollabItineraryApproval.member_id)
        .join(User, User.id == CollabMember.user_id)
        .where(CollabItineraryApproval.itinerary_id == plan.id, CollabMember.status == "ACTIVE")
    )
    trips = await session.scalars(
        select(CollabItineraryTrip).where(CollabItineraryTrip.collab_itinerary_id == plan.id)
    )
    trip_rows = list(trips.all())
    return {
        "id": plan.id,
        "title": plan.title,
        "status": plan.status,
        "version": plan.version,
        "items": item_payload,
        "approvals": [
            {"member_id": member.id, "email": user.email, "status": approval.status, "note": approval.note}
            for approval, member, user in approvals.all()
        ],
        "trip_ids": [trip.itinerary_id for trip in trip_rows],
        "trips": [
            {"user_id": trip.user_id, "itinerary_id": trip.itinerary_id}
            for trip in trip_rows
        ],
    }


@router.get("/groups", response_model=list[CollabGroupResponse])
async def get_my_groups(
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CollabGroupResponse]:
    groups = await list_groups(session, user.id)
    responses = []
    for group in groups:
        member = await session.scalar(
            select(CollabMember).where(
                CollabMember.group_id == group.id,
                CollabMember.user_id == user.id,
                CollabMember.status == "ACTIVE",
            )
        )
        if member is not None:
            responses.append(await group_response(session, group, member))
    return responses


@router.post("/groups", response_model=CollabGroupResponse, status_code=201)
async def create_collab_group(
    payload: CollabGroupCreate,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CollabGroupResponse:
    group, member = await create_group(session, user, payload)
    return await group_response(session, group, member)


@router.post("/join", response_model=CollabGroupResponse)
async def join_collab_group(
    payload: CollabJoinRequest,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CollabGroupResponse:
    group, member = await join_group(session, user, payload.invite_code)
    await publish_collab_event(group.id, "member_joined", {"member_id": member.id})
    return await group_response(session, group, member)


@router.get("/groups/{group_id}", response_model=CollabGroupResponse)
async def get_collab_group(
    group_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CollabGroupResponse:
    group, member = await _context(session, group_id, user)
    return await group_response(session, group, member)


@router.patch("/groups/{group_id}", response_model=CollabGroupResponse)
async def update_collab_group(
    group_id: str,
    payload: CollabGroupUpdate,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CollabGroupResponse:
    group, member = await _context(session, group_id, user)
    require_group_owner(member)
    changes = payload.model_dump(exclude_unset=True)
    for key in ("title", "objectives", "travel_mode"):
        if key in changes and changes[key] is None:
            raise ApiError(f"{key} cannot be null", status_code=422)
    start = changes.get("start_time", group.start_time)
    end = changes.get("end_time", group.end_time)
    if (start is None) != (end is None) or (start is not None and end is not None and end <= start):
        raise ApiError("Set both start and end times, with end after start", status_code=422)
    lat = changes.get("origin_latitude", group.origin_latitude)
    lng = changes.get("origin_longitude", group.origin_longitude)
    if (lat is None) != (lng is None):
        raise ApiError("Set both origin coordinates or clear both", status_code=422)
    for key, value in changes.items():
        setattr(group, key, value)
    if changes:
        await _reset_plan_review(session, group_id)
    await session.commit()
    await publish_collab_event(group_id, "group_updated", {})
    return await group_response(session, group, member)


@router.delete("/groups/{group_id}/members/{member_id}", status_code=204, response_class=Response)
async def remove_collab_member(
    group_id: str,
    member_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    group, requester = await _context(session, group_id, user)
    target = await session.scalar(
        select(CollabMember).where(
            CollabMember.id == member_id,
            CollabMember.group_id == group.id,
            CollabMember.status == "ACTIVE",
        )
    )
    if target is None:
        raise ApiError("Group member not found", status_code=404)
    if target.role == "owner":
        raise ApiError("The group owner cannot be removed", status_code=409)
    if requester.id != target.id:
        require_group_owner(requester)
    target.status = "REMOVED"
    await session.execute(delete(CollabWishlistReaction).where(CollabWishlistReaction.member_id == target.id))
    await session.execute(delete(CollabVote).where(CollabVote.member_id == target.id))
    await _reset_plan_review(session, group_id)
    await session.commit()
    await publish_collab_event(group_id, "member_removed", {"member_id": target.id})


@router.put("/groups/{group_id}/preferences")
async def update_my_collab_preferences(
    group_id: str,
    payload: CollabPreferencesUpdate,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    group, member = await _context(session, group_id, user)
    values = payload.model_dump()
    hard_keys = {"age", "budget_max", "max_distance_km", "accessibility_requirements"}
    record = await session.scalar(
        select(CollabMemberPreferences).where(CollabMemberPreferences.member_id == member.id)
    )
    if record is None:
        record = CollabMemberPreferences(member_id=member.id)
        session.add(record)
    # Preserve read-only fields copied from the member's existing traveler
    # preference record. These remain a Collab snapshot and never write back.
    soft = {
        key: value
        for key, value in (record.soft_preferences or {}).items()
        if key in {"category_slugs", "budget_sensitivity", "preferred_duration_minutes"}
    }
    soft.update({key: value for key, value in values.items() if key not in hard_keys})
    hard = {key: value for key, value in values.items() if key in hard_keys}
    record.soft_preferences = soft
    record.hard_constraints = hard
    await _reset_plan_review(session, group.id)
    await session.commit()
    await publish_collab_event(group.id, "preferences_updated", {"member_id": member.id})
    return {"member_id": member.id, "soft_preferences": soft, "hard_constraints": hard}


@router.get("/groups/{group_id}/preference-analysis", response_model=PreferenceAnalysisResponse)
async def get_preference_analysis(
    group_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PreferenceAnalysisResponse:
    group, member = await _context(session, group_id, user)
    snapshot = await group_response(session, group, member)
    return PreferenceAnalysisResponse(
        **analyze_group_preferences([member.model_dump() for member in snapshot.members])
    )


@router.get("/groups/{group_id}/recommendations", response_model=CollabRecommendationResponse)
async def get_group_recommendations(
    group_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
    query: Annotated[str | None, Query(max_length=200)] = None,
    category_slug: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 24,
) -> CollabRecommendationResponse:
    group, _member = await _context(session, group_id, user)
    return await recommend_for_group(
        session=session,
        settings=settings,
        routing=routing,
        group=group,
        requester_user_id=user.id,
        query=query,
        category_slug=category_slug,
        limit=limit,
    )


@router.get("/groups/{group_id}/wishlist")
async def get_collab_wishlist(
    group_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    _group, member = await _context(session, group_id, user)
    items = await session.scalars(
        select(CollabWishlistItem)
        .where(CollabWishlistItem.group_id == group_id)
        .order_by(CollabWishlistItem.created_at.desc())
    )
    return [await _serialize_wishlist_item(session, item, member.id) for item in items.all()]


@router.post("/groups/{group_id}/wishlist", status_code=201)
async def add_collab_wishlist_item(
    group_id: str,
    payload: CollabWishlistAddRequest,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    _group, member = await _context(session, group_id, user)
    await _get_real_experience(session, payload.experience_id)
    item = await session.scalar(
        select(CollabWishlistItem).where(
            CollabWishlistItem.group_id == group_id,
            CollabWishlistItem.experience_id == payload.experience_id,
        )
    )
    if item is None:
        item = CollabWishlistItem(
            group_id=group_id,
            experience_id=payload.experience_id,
            added_by_member_id=member.id,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        await publish_collab_event(group_id, "wishlist_updated", {"experience_id": item.experience_id})
    return await _serialize_wishlist_item(session, item, member.id)


@router.delete("/groups/{group_id}/wishlist/{item_id}", status_code=204, response_class=Response)
async def remove_collab_wishlist_item(
    group_id: str,
    item_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    _group, member = await _context(session, group_id, user)
    item = await session.scalar(
        select(CollabWishlistItem).where(CollabWishlistItem.id == item_id, CollabWishlistItem.group_id == group_id)
    )
    if item is None:
        raise ApiError("Wishlist item not found", status_code=404)
    if member.role != "owner" and item.added_by_member_id != member.id:
        raise ApiError("Only the owner or the member who added this item can remove it", status_code=403)
    plan = await _plan_for_group(session, group_id)
    if plan is not None and plan.status == "FINALIZED":
        raise ApiError("The finalized group's wishlist is read-only", status_code=409)
    if plan is not None:
        selected_rows = list((await session.scalars(
            select(CollabItineraryItem)
            .where(
                CollabItineraryItem.itinerary_id == plan.id,
                CollabItineraryItem.experience_id == item.experience_id,
            )
        )).all())
        if selected_rows:
            await session.execute(
                delete(CollabItineraryItem).where(
                    CollabItineraryItem.itinerary_id == plan.id,
                    CollabItineraryItem.experience_id == item.experience_id,
                )
            )
            await session.flush()
            remaining = list((await session.scalars(
                select(CollabItineraryItem)
                .where(CollabItineraryItem.itinerary_id == plan.id)
                .order_by(CollabItineraryItem.sequence_order)
            )).all())
            for position, plan_item in enumerate(remaining, start=1):
                plan_item.sequence_order = -position
            await session.flush()
            for position, plan_item in enumerate(remaining, start=1):
                plan_item.sequence_order = position
            plan.status = "DRAFT"
            plan.version += 1
            await session.execute(delete(CollabItineraryApproval).where(CollabItineraryApproval.itinerary_id == plan.id))
    await session.delete(item)
    await session.commit()
    await publish_collab_event(group_id, "wishlist_updated", {"item_id": item_id})


@router.put("/groups/{group_id}/wishlist/{item_id}/reaction")
async def react_to_collab_wishlist_item(
    group_id: str,
    item_id: str,
    payload: CollabReactionRequest,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    _group, member = await _context(session, group_id, user)
    item = await session.scalar(
        select(CollabWishlistItem).where(CollabWishlistItem.id == item_id, CollabWishlistItem.group_id == group_id)
    )
    if item is None:
        raise ApiError("Wishlist item not found", status_code=404)
    reaction = await session.scalar(
        select(CollabWishlistReaction).where(
            CollabWishlistReaction.wishlist_item_id == item_id,
            CollabWishlistReaction.member_id == member.id,
        )
    )
    if reaction is None:
        reaction = CollabWishlistReaction(wishlist_item_id=item_id, member_id=member.id, reaction=payload.reaction)
        session.add(reaction)
    else:
        reaction.reaction = payload.reaction
    await session.commit()
    await publish_collab_event(group_id, "wishlist_reaction", {"item_id": item_id, "member_id": member.id})
    return {"item_id": item_id, "reaction": payload.reaction}


@router.get("/groups/{group_id}/decisions")
async def get_collab_decisions(
    group_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    await _context(session, group_id, user)
    decisions = await session.scalars(
        select(CollabDecision).where(CollabDecision.group_id == group_id).order_by(CollabDecision.created_at.desc())
    )
    return [await _serialize_decision(session, decision) for decision in decisions.all()]


@router.post("/groups/{group_id}/decisions", status_code=201)
async def create_collab_decision(
    group_id: str,
    payload: CollabDecisionCreate,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    _group, member = await _context(session, group_id, user)
    if len({option.experience_id for option in payload.options if option.experience_id}) != sum(
        option.experience_id is not None for option in payload.options
    ):
        raise ApiError("An experience can appear only once in a decision", status_code=422)
    decision = CollabDecision(group_id=group_id, created_by_member_id=member.id, title=payload.title.strip())
    session.add(decision)
    await session.flush()
    for option in payload.options:
        label = option.label.strip()
        if option.experience_id:
            experience = await _get_real_experience(session, option.experience_id)
            label = experience.title
        session.add(
            CollabDecisionOption(decision_id=decision.id, experience_id=option.experience_id, label=label)
        )
    await session.commit()
    await session.refresh(decision)
    await publish_collab_event(group_id, "decision_created", {"decision_id": decision.id})
    return await _serialize_decision(session, decision)


@router.put("/groups/{group_id}/decisions/{decision_id}/vote")
async def vote_collab_decision(
    group_id: str,
    decision_id: str,
    payload: CollabVoteRequest,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    _group, member = await _context(session, group_id, user)
    decision = await session.scalar(
        select(CollabDecision).where(CollabDecision.id == decision_id, CollabDecision.group_id == group_id)
    )
    option = await session.scalar(
        select(CollabDecisionOption).where(
            CollabDecisionOption.id == payload.option_id,
            CollabDecisionOption.decision_id == decision_id,
        )
    )
    if decision is None or option is None:
        raise ApiError("Decision option not found", status_code=404)
    if decision.status != "OPEN":
        raise ApiError("This decision is closed", status_code=409)
    vote = await session.scalar(
        select(CollabVote).where(CollabVote.decision_id == decision_id, CollabVote.member_id == member.id)
    )
    if vote is None:
        vote = CollabVote(decision_id=decision_id, option_id=option.id, member_id=member.id)
        session.add(vote)
    else:
        vote.option_id = option.id
    await session.commit()
    await publish_collab_event(group_id, "vote_updated", {"decision_id": decision_id, "member_id": member.id})
    return {"decision_id": decision_id, "option_id": option.id}


@router.post("/groups/{group_id}/decisions/{decision_id}/close")
async def close_collab_decision(
    group_id: str,
    decision_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    _group, member = await _context(session, group_id, user)
    require_group_owner(member)
    decision = await session.scalar(
        select(CollabDecision).where(CollabDecision.id == decision_id, CollabDecision.group_id == group_id)
    )
    if decision is None:
        raise ApiError("Decision not found", status_code=404)
    decision.status = "CLOSED"
    await session.commit()
    await publish_collab_event(group_id, "decision_closed", {"decision_id": decision_id})
    return {"decision_id": decision_id, "status": decision.status}


@router.get("/groups/{group_id}/itinerary")
async def get_collab_itinerary(
    group_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any] | None:
    await _context(session, group_id, user)
    return await _serialize_plan(session, await _plan_for_group(session, group_id))


@router.put("/groups/{group_id}/itinerary")
async def update_collab_itinerary(
    group_id: str,
    payload: CollabItineraryUpdate,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    _group, member = await _context(session, group_id, user)
    ids = [item.experience_id for item in payload.items]
    if len(set(ids)) != len(ids):
        raise ApiError("An activity can appear only once in the itinerary", status_code=422)
    wishlist_ids = set(
        (await session.scalars(
            select(CollabWishlistItem.experience_id).where(
                CollabWishlistItem.group_id == group_id,
                CollabWishlistItem.experience_id.in_(ids),
            )
        )).all()
    )
    if wishlist_ids != set(ids):
        raise ApiError("Add every itinerary activity to the shared wishlist first", status_code=422)
    for experience_id in ids:
        await _get_real_experience(session, experience_id)

    plan = await _plan_for_group(session, group_id)
    if plan is not None and plan.status == "FINALIZED":
        raise ApiError("This collaborative itinerary is already finalized", status_code=409)
    if plan is None:
        plan = CollabItinerary(group_id=group_id, created_by_member_id=member.id, title=payload.title.strip())
        session.add(plan)
        await session.flush()
    else:
        plan.title = payload.title.strip()
        plan.status = "REVIEW"
        plan.version += 1
        await session.execute(delete(CollabItineraryItem).where(CollabItineraryItem.itinerary_id == plan.id))
        await session.execute(delete(CollabItineraryApproval).where(CollabItineraryApproval.itinerary_id == plan.id))

    for position, item in enumerate(payload.items, start=1):
        session.add(
            CollabItineraryItem(
                itinerary_id=plan.id,
                experience_id=item.experience_id,
                sequence_order=position,
                is_optional=item.is_optional,
            )
        )
    for active_member in await _active_members(session, group_id):
        session.add(CollabItineraryApproval(itinerary_id=plan.id, member_id=active_member.id, status="PENDING"))
    plan.status = "REVIEW"
    await session.commit()
    await session.refresh(plan)
    await publish_collab_event(group_id, "itinerary_updated", {"itinerary_id": plan.id, "version": plan.version})
    return await _serialize_plan(session, plan) or {}


@router.put("/groups/{group_id}/itinerary/approval")
async def review_collab_itinerary(
    group_id: str,
    payload: CollabItineraryApprovalUpdate,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    _group, member = await _context(session, group_id, user)
    plan = await _plan_for_group(session, group_id)
    if plan is None or plan.status in {"DRAFT", "FINALIZED"}:
        raise ApiError("An editable collaborative itinerary was not found", status_code=404)
    approval = await session.scalar(
        select(CollabItineraryApproval).where(
            CollabItineraryApproval.itinerary_id == plan.id,
            CollabItineraryApproval.member_id == member.id,
        )
    )
    if approval is None:
        approval = CollabItineraryApproval(itinerary_id=plan.id, member_id=member.id)
        session.add(approval)
    approval.status = payload.status
    approval.note = payload.note
    plan.status = "REVIEW"
    await session.commit()
    await publish_collab_event(group_id, "member_reviewed_itinerary", {"member_id": member.id})
    return await _serialize_plan(session, plan) or {}


@router.post("/groups/{group_id}/itinerary/finalize")
async def finalize_collab_itinerary(
    group_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
    ai: Annotated[AIAdapter, Depends(get_ai_adapter)],
) -> dict[str, Any]:
    group, member = await _context(session, group_id, user)
    plan = await _plan_for_group(session, group_id)
    if plan is None:
        raise ApiError("Create a collaborative itinerary before finalizing", status_code=404)
    active_members = await _active_members(session, group_id)
    approvals = await session.scalars(
        select(CollabItineraryApproval).where(CollabItineraryApproval.itinerary_id == plan.id)
    )
    approved_member_ids = {approval.member_id for approval in approvals.all() if approval.status == "APPROVED"}
    if approved_member_ids != {active_member.id for active_member in active_members}:
        raise ApiError("Every active member must approve the current plan before it can be finalized", status_code=409)
    plan_items = list(
        (await session.scalars(
            select(CollabItineraryItem)
            .where(CollabItineraryItem.itinerary_id == plan.id)
            .order_by(CollabItineraryItem.sequence_order)
        )).all()
    )
    itineraries = await finalize_collab_plan(
        session=session,
        settings=settings,
        routing=routing,
        ai=ai,
        group=group,
        plan=plan,
        active_members=active_members,
        plan_items=plan_items,
        requester_member=member,
    )
    await publish_collab_event(
        group_id,
        "itinerary_finalized",
        {"collab_itinerary_id": plan.id, "trip_ids": [itinerary.id for itinerary in itineraries]},
    )
    latest_plan = await _serialize_plan(session, plan) or {}
    return {
        "status": plan.status,
        "trip_ids": [itinerary.id for itinerary in itineraries],
        "trips": latest_plan.get("trips", []),
    }


@router.get("/groups/{group_id}/events")
async def collab_group_events(
    group_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    await _context(session, group_id, user)
    return StreamingResponse(
        sse_collab_updates_stream(group_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]
