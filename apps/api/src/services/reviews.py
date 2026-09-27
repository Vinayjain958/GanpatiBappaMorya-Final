"""Traveler-submitted review orchestration.

Distinct from the Phase 12 synthetic review generator
(src/services/synthetic_experience_enrichment.py): this handles a real
user submitting a real review through the API. Author identity, source
provenance, and the synthetic flag are always server-derived — never
accepted from the request body — so a caller can't forge a synthetic-
looking or third-party review (see ReviewCreateRequest).

The Experience's aggregate rating/review_count are recomputed from the
full set of ExperienceReview rows after every write, so they never drift
from what list_experience_reviews would show (the same invariant the
synthetic enrichment script relies on).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.display_name import derive_display_name
from src.core.errors import ApiError
from src.models.experience import Experience
from src.models.review import ExperienceReview
from src.models.user import User
from src.repositories.experience_repository import ExperienceRepository
from src.repositories.review_repository import ReviewRepository
from src.schemas.experience import ReviewCreateRequest

USER_REVIEW_SOURCE_TYPE = "user_submitted"
USER_REVIEW_SOURCE_NAME = "LocaLens traveler review"


async def submit_review(
    session: AsyncSession,
    experience_id: str,
    user: User,
    payload: ReviewCreateRequest,
) -> tuple[ExperienceReview, Experience]:
    experience_repo = ExperienceRepository(session)
    experience = await experience_repo.get_by_id(experience_id)
    if experience is None:
        raise ApiError("Experience not found", status_code=404)

    review_repo = ReviewRepository(session)

    # generation_version="user" keeps real reviews in their own sequence
    # space, distinct from the synthetic generator's "v1"/"v2".../ so
    # --regenerate-synthetic (which only touches source_type=
    # synthetic_enrichment rows) can never delete a real review, and a
    # second real review never collides with uq_experience_review_synthetic_seq.
    next_sequence = await review_repo.next_synthetic_sequence(experience_id, "user")

    review = ExperienceReview(
        experience_id=experience_id,
        rating_value=payload.rating_value,
        title=payload.title,
        body=payload.body,
        author_display_name=derive_display_name(user),
        language="en",
        reviewed_at=datetime.now(UTC),
        source_type=USER_REVIEW_SOURCE_TYPE,
        source_name=USER_REVIEW_SOURCE_NAME,
        is_synthetic=False,
        is_enriched=False,
        generation_version="user",
        synthetic_sequence=next_sequence,
    )
    review_repo.add(review)
    await session.flush()

    avg_rating, review_count, _distribution = await review_repo.get_distribution_and_avg(
        experience_id
    )
    has_synthetic = await review_repo.has_synthetic_reviews(experience_id)
    experience.rating = avg_rating
    experience.review_count = review_count
    experience.rating_source = "mixed" if has_synthetic else "user_submitted"

    await session.commit()
    await session.refresh(review)
    await session.refresh(experience)
    return review, experience
