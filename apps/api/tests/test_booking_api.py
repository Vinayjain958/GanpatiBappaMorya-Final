"""Booking-request API tests (Phase 8). REQUESTED intent only — proves no
payment fields exist and REQUESTED/ACCEPTED are never rendered as
CONFIRMED."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from src.models.itinerary import Itinerary
from src.models.itinerary_item import ItineraryItem
from tests.conftest import auth_header, register_provider, register_traveler


async def _seed_itinerary_with_item(session_factory, traveler_id: str, experience_id: str, provider_id: str):
    async def _seed():
        async with session_factory() as session:
            from datetime import time

            itinerary = Itinerary(
                traveler_id=traveler_id,
                title="Test Itinerary",
                itinerary_date=datetime(2026, 10, 12).date(),
                start_time=time(9, 0),
                end_time=time(18, 0),
                status="VALIDATED",
                source="COMPOSER",
                currency="INR",
            )
            session.add(itinerary)
            await session.flush()

            item = ItineraryItem(
                itinerary_id=itinerary.id,
                experience_id=experience_id,
                sequence_order=1,
                planned_start=datetime(2026, 10, 12, 10, 0, tzinfo=UTC),
                planned_end=datetime(2026, 10, 12, 11, 0, tzinfo=UTC),
                duration_minutes=60,
                buffer_before_minutes=0,
                buffer_after_minutes=0,
                estimated_cost=200.0,
            )
            session.add(item)
            await session.commit()
            return itinerary.id, item.id

    return await _seed()


def _fixture_with_client_session(discovery_client, discovery_dataset, session_factory):
    return discovery_client, discovery_dataset, session_factory


def test_create_booking_requires_auth(discovery_client) -> None:
    response = discovery_client.post(
        "/api/v1/itineraries/some-id/booking-requests", json={"itinerary_item_id": "x"}
    )
    assert response.status_code == 401


def test_create_booking_happy_path(discovery_client, discovery_dataset, session_factory) -> None:
    user = register_traveler(discovery_client, "booking-traveler@example.com")
    traveler_id = discovery_client.get("/api/v1/auth/me", headers=auth_header(user)).json()["traveler"]["id"]

    itinerary_id, item_id = asyncio.run(
        _seed_itinerary_with_item(
            session_factory, traveler_id, discovery_dataset["near_experience_id"], discovery_dataset["provider_id"]
        )
    )

    response = discovery_client.post(
        f"/api/v1/itineraries/{itinerary_id}/booking-requests",
        json={"itinerary_item_id": item_id, "party_size": 2},
        headers=auth_header(user),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "REQUESTED"
    # No payment fields anywhere in the response.
    payment_markers = {"payment", "card", "stripe", "razorpay", "amount_paid", "payment_intent"}
    assert not (payment_markers & set(body.keys()))


def test_wrong_itinerary_ownership_rejected(discovery_client, discovery_dataset, session_factory) -> None:
    owner = register_traveler(discovery_client, "booking-owner@example.com")
    intruder = register_traveler(discovery_client, "booking-intruder@example.com")
    owner_traveler_id = discovery_client.get("/api/v1/auth/me", headers=auth_header(owner)).json()["traveler"]["id"]

    itinerary_id, item_id = asyncio.run(
        _seed_itinerary_with_item(
            session_factory, owner_traveler_id, discovery_dataset["near_experience_id"], discovery_dataset["provider_id"]
        )
    )

    response = discovery_client.post(
        f"/api/v1/itineraries/{itinerary_id}/booking-requests",
        json={"itinerary_item_id": item_id},
        headers=auth_header(intruder),
    )
    assert response.status_code == 404


def test_provider_sees_only_own_requests(discovery_client, discovery_dataset, session_factory) -> None:
    user = register_traveler(discovery_client, "booking-provider-test@example.com")
    traveler_id = discovery_client.get("/api/v1/auth/me", headers=auth_header(user)).json()["traveler"]["id"]

    itinerary_id, item_id = asyncio.run(
        _seed_itinerary_with_item(
            session_factory, traveler_id, discovery_dataset["near_experience_id"], discovery_dataset["provider_id"]
        )
    )
    discovery_client.post(
        f"/api/v1/itineraries/{itinerary_id}/booking-requests",
        json={"itinerary_item_id": item_id},
        headers=auth_header(user),
    )

    # A different, unrelated provider must see zero booking requests.
    other_provider = register_provider(discovery_client, "unrelated-provider@example.com", "Unrelated Biz")
    response = discovery_client.get("/api/v1/provider/booking-requests", headers=auth_header(other_provider))
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def _seed_experience_for_provider(session_factory, provider_user_email: str):
    """Seeds an Experience owned by the Provider row linked to a
    just-registered provider User (so the accept/decline HTTP round-trip
    can authenticate as the real owning provider)."""

    async def _seed():
        async with session_factory() as session:
            from sqlalchemy import select

            from src.models.category import ExperienceCategory
            from src.models.experience import Experience
            from src.models.location import Location
            from src.models.provider import Provider
            from src.models.user import User

            user = (await session.execute(select(User).where(User.email == provider_user_email))).scalar_one()
            provider = (
                await session.execute(select(Provider).where(Provider.user_id == user.id))
            ).scalar_one()

            category = ExperienceCategory(slug="booking-test-cat", name="Booking Test", sort_order=99)
            session.add(category)
            location = Location(
                latitude=18.93, longitude=72.83, city="Mumbai", locality="Fort",
                source_type="synthetic", is_synthetic=True,
            )
            session.add(location)
            await session.flush()

            experience = Experience(
                provider_id=provider.id, category=category, location=location,
                title="Booking Test Experience", short_description="x", full_description="x",
                currency="INR", price=200.0, price_type="fixed", price_source="estimated",
                is_price_estimated=True, duration_minutes=60, duration_is_estimated=True,
                status="active", verification_status="unverified", opening_hours_status="unavailable",
                source_type="synthetic", is_synthetic=True,
            )
            session.add(experience)
            await session.commit()
            return experience.id, provider.id

    return await _seed()


def test_provider_accept_decline(discovery_client, discovery_dataset, session_factory) -> None:
    traveler = register_traveler(discovery_client, "booking-accept-traveler@example.com")
    traveler_id = discovery_client.get("/api/v1/auth/me", headers=auth_header(traveler)).json()["traveler"]["id"]

    provider_user = register_provider(discovery_client, "booking-accept-provider@example.com", "Accept Biz")
    experience_id, provider_id = asyncio.run(
        _seed_experience_for_provider(session_factory, "booking-accept-provider@example.com")
    )

    itinerary_id, item_id = asyncio.run(
        _seed_itinerary_with_item(session_factory, traveler_id, experience_id, provider_id)
    )
    create_resp = discovery_client.post(
        f"/api/v1/itineraries/{itinerary_id}/booking-requests",
        json={"itinerary_item_id": item_id},
        headers=auth_header(traveler),
    )
    assert create_resp.status_code == 201, create_resp.text
    booking_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "REQUESTED"
    assert create_resp.json()["status"] != "CONFIRMED"

    # A different provider cannot modify this request.
    other_provider = register_provider(discovery_client, "booking-other-provider@example.com", "Other Biz")
    forbidden_resp = discovery_client.patch(
        f"/api/v1/provider/booking-requests/{booking_id}",
        json={"status": "ACCEPTED"},
        headers=auth_header(other_provider),
    )
    assert forbidden_resp.status_code == 404

    # The owning provider CAN accept it.
    accept_resp = discovery_client.patch(
        f"/api/v1/provider/booking-requests/{booking_id}",
        json={"status": "ACCEPTED"},
        headers=auth_header(provider_user),
    )
    assert accept_resp.status_code == 200, accept_resp.text
    assert accept_resp.json()["status"] == "ACCEPTED"
    # ACCEPTED is still never CONFIRMED.
    assert accept_resp.json()["status"] != "CONFIRMED"

    # Cannot double-respond to an already-ACCEPTED request.
    second_resp = discovery_client.patch(
        f"/api/v1/provider/booking-requests/{booking_id}",
        json={"status": "DECLINED"},
        headers=auth_header(provider_user),
    )
    assert second_resp.status_code == 422


def test_anonymous_cannot_list_own_bookings(discovery_client) -> None:
    response = discovery_client.get("/api/v1/bookings/me")
    assert response.status_code == 401


def test_no_payment_fields_in_schema() -> None:
    from src.schemas.booking import BookingRequestCreate, BookingRequestResponse

    for schema in (BookingRequestCreate, BookingRequestResponse):
        fields = set(schema.model_fields.keys())
        payment_markers = {"payment", "card_number", "cvv", "stripe_id", "razorpay_id", "amount_paid"}
        assert not (payment_markers & fields)


def test_requested_status_never_equals_confirmed() -> None:
    import typing

    from src.schemas.booking import BookingStatusLiteral

    allowed = typing.get_args(BookingStatusLiteral)
    assert "CONFIRMED" not in allowed
    assert "REQUESTED" in allowed
