"""Booking-request endpoints (Phase 8).

REQUESTED intent only. A traveler can create a booking request against an
itinerary item they own; a provider can ACCEPT/DECLINE a request only for
an experience their own Provider profile owns (mirrors the provider
ownership pattern in src/api/v1/providers.py). No payment processing
anywhere in this module; ACCEPTED is never rendered/returned as
"CONFIRMED" (docs/DECISIONS.md ADR-046).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.db import get_session
from src.core.deps import CurrentProvider, require_traveler
from src.core.errors import ApiError
from src.models.booking_request import BookingRequest
from src.models.user import User
from src.repositories.booking_repository import BookingRequestRepository
from src.repositories.experience_repository import ExperienceRepository
from src.repositories.itinerary_item_repository import ItineraryItemRepository
from src.repositories.itinerary_repository import ItineraryRepository
from src.schemas.booking import (
    BookingRequestCreate,
    BookingRequestListResponse,
    BookingRequestResponse,
    BookingStatusUpdate,
)
from src.services.provider_intelligence.notifications import ProviderNotificationService

router = APIRouter(tags=["bookings"])


async def _to_response(session: AsyncSession, booking: BookingRequest) -> BookingRequestResponse:
    exp = await ExperienceRepository(session).get_by_id(booking.experience_id)
    resp = BookingRequestResponse.model_validate(booking)
    resp.experience_title = exp.title if exp else None
    return resp


@router.post("/itineraries/{itinerary_id}/booking-requests", response_model=BookingRequestResponse, status_code=201)
async def create_booking_request(
    itinerary_id: str,
    payload: BookingRequestCreate,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BookingRequestResponse:
    traveler_id = user.traveler.id
    itinerary = await ItineraryRepository(session).get_owned_by_id(itinerary_id, traveler_id)
    if itinerary is None:
        raise ApiError("Itinerary not found", status_code=404)

    item = await ItineraryItemRepository(session).get_by_id(payload.itinerary_item_id)
    if item is None or item.itinerary_id != itinerary.id:
        raise ApiError("Itinerary item not found", status_code=404)

    experience = await ExperienceRepository(session).get_by_id(item.experience_id)
    if experience is None:
        raise ApiError("Experience not found", status_code=404)
    if experience.status != "active":
        raise ApiError("This experience is no longer bookable.", status_code=422)

    booking = BookingRequest(
        traveler_id=traveler_id,
        itinerary_id=itinerary.id,
        itinerary_item_id=item.id,
        experience_id=experience.id,
        provider_id=experience.provider_id,
        requested_start=item.planned_start,
        requested_end=item.planned_end,
        party_size=payload.party_size,
        traveler_note=payload.traveler_note,
        status="REQUESTED",
        requested_at=datetime.now(UTC),
    )
    BookingRequestRepository(session).add(booking)
    itinerary.status = "BOOKING_REQUESTED"
    
    # Phase 10: notify provider of booking request
    notification_svc = ProviderNotificationService(session, settings)
    await notification_svc.notify_booking_request(booking, experience)

    await session.commit()
    await session.refresh(booking)
    return await _to_response(session, booking)


@router.get("/bookings/me", response_model=BookingRequestListResponse)
async def list_my_booking_requests(
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BookingRequestListResponse:
    rows, total = await BookingRequestRepository(session).list_by_traveler(user.traveler.id)
    items = [await _to_response(session, row) for row in rows]
    return BookingRequestListResponse(items=items, total=total)


@router.get("/provider/booking-requests", response_model=BookingRequestListResponse)
async def list_provider_booking_requests(
    provider: CurrentProvider,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BookingRequestListResponse:
    rows, total = await BookingRequestRepository(session).list_by_provider(provider.id)
    items = [await _to_response(session, row) for row in rows]
    return BookingRequestListResponse(items=items, total=total)


@router.patch("/provider/booking-requests/{booking_id}", response_model=BookingRequestResponse)
async def update_provider_booking_request(
    booking_id: str,
    payload: BookingStatusUpdate,
    provider: CurrentProvider,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BookingRequestResponse:
    repo = BookingRequestRepository(session)
    booking = await repo.get_owned_by_provider(booking_id, provider.id)
    if booking is None:
        # Never disclose existence of another provider's booking request.
        raise ApiError("Booking request not found", status_code=404)
    if booking.status != "REQUESTED":
        raise ApiError(f"Booking request is already {booking.status}.", status_code=422)

    booking.status = payload.status
    booking.provider_note = payload.provider_note
    booking.responded_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(booking)
    return await _to_response(session, booking)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingRequestResponse)
async def cancel_booking_request(
    booking_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BookingRequestResponse:
    repo = BookingRequestRepository(session)
    booking = await repo.get_owned_by_traveler(booking_id, user.traveler.id)
    if booking is None:
        raise ApiError("Booking request not found", status_code=404)
    if booking.status not in ("REQUESTED", "ACCEPTED"):
        raise ApiError(f"Booking request cannot be cancelled from status {booking.status}.", status_code=422)

    booking.status = "CANCELLED"
    booking.responded_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(booking)
    return await _to_response(session, booking)
