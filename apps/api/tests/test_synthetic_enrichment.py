from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo
import pytest

from src.models.category import ExperienceCategory
from src.models.experience import Experience
from src.models.opening_hour import ExperienceOpeningHour
from src.models.review import ExperienceReview
from src.services.synthetic_experience_enrichment import (
    generate_synthetic_availability_slots,
    generate_synthetic_opening_hours,
    generate_synthetic_reviews,
    get_seeded_rng,
)

_MUMBAI_TZ = ZoneInfo("Asia/Kolkata")


def _make_dummy_experience(
    experience_id: str = "exp-123",
    slug: str = "cafes",
    duration: int = 60,
    capacity: int = 20,
) -> Experience:
    exp = Experience(
        id=experience_id,
        title="Test Cafe Experience",
        short_description="A cozy cafe in Mumbai",
        full_description="Long description of the cozy cafe experience in Bandra, Mumbai.",
        category_id="cat-1",
        provider_id="prov-1",
        location_id="loc-1",
        currency="INR",
        price=500.0,
        price_type="per_person",
        duration_minutes=duration,
        capacity=capacity,
        status="active",
        verification_status="verified",
        source_type="synthetic",
        is_synthetic=True,
        is_enriched=False,
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    exp.category = ExperienceCategory(id="cat-1", slug=slug, name=slug.capitalize())
    return exp


def test_seeded_rng_determinism() -> None:
    rng1 = get_seeded_rng("exp-123")
    rng2 = get_seeded_rng("exp-123")
    assert [rng1.random() for _ in range(10)] == [rng2.random() for _ in range(10)]

    rng3 = get_seeded_rng("exp-456")
    rng4 = get_seeded_rng("exp-123")
    assert [rng4.random() for _ in range(5)] != [rng3.random() for _ in range(5)]


def test_synthetic_reviews_generation_and_mathematical_consistency() -> None:
    exp = _make_dummy_experience(experience_id="exp-test-cafe", slug="cafes")
    rng = get_seeded_rng(exp.id)

    reviews = generate_synthetic_reviews(exp, rng)

    assert 6 <= len(reviews) <= 65
    assert all(isinstance(r, ExperienceReview) for r in reviews)
    assert all(r.experience_id == exp.id for r in reviews)
    assert all(r.is_synthetic is True for r in reviews)
    assert all(r.source_type == "synthetic_enrichment" for r in reviews)
    assert all(1 <= r.rating_value <= 5 for r in reviews)

    # Sequence numbering is sequential
    sequences = [r.synthetic_sequence for r in reviews]
    assert sequences == list(range(len(reviews)))

    # Mathematical average consistency
    avg_rating = round(sum(r.rating_value for r in reviews) / len(reviews), 1)
    assert 3.0 <= avg_rating <= 5.0


def test_synthetic_reviews_determinism() -> None:
    exp1 = _make_dummy_experience(experience_id="exp-fixed-id", slug="adventure")
    exp2 = _make_dummy_experience(experience_id="exp-fixed-id", slug="adventure")

    rng1 = get_seeded_rng(exp1.id)
    rng2 = get_seeded_rng(exp2.id)

    reviews_1 = generate_synthetic_reviews(exp1, rng1)
    reviews_2 = generate_synthetic_reviews(exp2, rng2)

    assert len(reviews_1) == len(reviews_2)
    assert [r.rating_value for r in reviews_1] == [r.rating_value for r in reviews_2]
    assert [r.title for r in reviews_1] == [r.title for r in reviews_2]
    assert [r.body for r in reviews_1] == [r.body for r in reviews_2]


def test_natural_review_text_and_rating_alignment() -> None:
    exp = _make_dummy_experience(experience_id="exp-street-food", slug="street-food")
    rng = get_seeded_rng(exp.id)
    reviews = generate_synthetic_reviews(exp, rng)

    lengths = [len(r.body.split()) for r in reviews]
    assert min(lengths) < 30  # short reviews exist
    assert max(lengths) >= 20

    # Ensure low star reviews don't claim pure perfection
    for r in reviews:
        if r.rating_value <= 2:
            assert any(
                crit in r.body.lower()
                for crit in ["crowd", "wait", "noisy", "pricey", "hectic", "seating", "overwhelm", "chaotic", "sun", "humid", "tiring"]
            )


def test_opening_hours_generation_and_overnight_validity() -> None:
    exp = _make_dummy_experience(experience_id="exp-nightlife", slug="nightlife")
    rng = get_seeded_rng(exp.id)
    hours = generate_synthetic_opening_hours(exp, rng)

    assert len(hours) == 7
    days = {h.day_of_week for h in hours}
    assert days == set(range(7))

    # Nightlife should have open hours extending late
    open_windows = [h for h in hours if not h.is_closed]
    assert len(open_windows) > 0
    for h in open_windows:
        assert h.open_time is not None
        assert h.close_time is not None


def test_availability_slots_fit_opening_windows() -> None:
    exp = _make_dummy_experience(experience_id="exp-museum", slug="museums", duration=90, capacity=25)
    rng_hours = get_seeded_rng(exp.id)
    hours_schedules = generate_synthetic_opening_hours(exp, rng_hours)

    hours_models = [
        ExperienceOpeningHour(
            experience_id=exp.id,
            day_of_week=h.day_of_week,
            open_time=h.open_time,
            close_time=h.close_time,
            is_closed=h.is_closed,
            source_type="synthetic_enrichment",
            is_synthetic=True,
        )
        for h in hours_schedules
    ]

    rng_slots = get_seeded_rng(exp.id)
    slots = generate_synthetic_availability_slots(
        experience=exp,
        opening_hours=hours_models,
        rng=rng_slots,
        days_forward=14,
    )

    assert len(slots) > 0
    assert all(s.experience_id == exp.id for s in slots)
    assert all(s.is_synthetic is True for s in slots)
    assert all(s.source_type == "synthetic_enrichment" for s in slots)

    closed_days = {h.day_of_week for h in hours_models if h.is_closed}

    for slot in slots:
        assert slot.starts_at < slot.ends_at
        assert slot.capacity == exp.capacity
        assert 0 <= slot.available_slots <= slot.capacity

        # Check in local Mumbai time that slot does not start on a closed day
        slot_local = slot.starts_at.astimezone(_MUMBAI_TZ)
        assert slot_local.weekday() not in closed_days
