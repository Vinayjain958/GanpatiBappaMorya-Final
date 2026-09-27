from __future__ import annotations

from typing import Literal
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.review import ExperienceReview

SortOrder = Literal["newest", "highest", "lowest"]


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_experience(
        self,
        experience_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        sort: SortOrder = "newest",
    ) -> tuple[list[ExperienceReview], int]:
        count_query = (
            select(func.count(ExperienceReview.id))
            .where(ExperienceReview.experience_id == experience_id)
        )
        total = (await self._session.execute(count_query)).scalar_one()

        query = select(ExperienceReview).where(ExperienceReview.experience_id == experience_id)

        if sort == "highest":
            query = query.order_by(
                ExperienceReview.rating_value.desc(),
                ExperienceReview.reviewed_at.desc(),
                ExperienceReview.id.asc(),
            )
        elif sort == "lowest":
            query = query.order_by(
                ExperienceReview.rating_value.asc(),
                ExperienceReview.reviewed_at.desc(),
                ExperienceReview.id.asc(),
            )
        else:  # newest
            query = query.order_by(
                ExperienceReview.reviewed_at.desc(),
                ExperienceReview.id.asc(),
            )

        query = query.limit(limit).offset(offset)
        rows = (await self._session.execute(query)).scalars().all()
        return list(rows), total

    async def get_distribution_and_avg(
        self, experience_id: str
    ) -> tuple[float | None, int, dict[int, int]]:
        query = (
            select(ExperienceReview.rating_value, func.count(ExperienceReview.id))
            .where(ExperienceReview.experience_id == experience_id)
            .group_by(ExperienceReview.rating_value)
        )
        rows = (await self._session.execute(query)).all()
        distribution: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        total_count = 0
        total_sum = 0
        for star, count in rows:
            if star in distribution:
                distribution[star] = count
            total_count += count
            total_sum += star * count

        if total_count == 0:
            return None, 0, distribution

        avg = round(total_sum / total_count, 1)
        return avg, total_count, distribution

    async def get_real_review_count(self, experience_id: str) -> int:
        """Count reviews with real provenance for evidence labels."""
        query = select(func.count(ExperienceReview.id)).where(
            ExperienceReview.experience_id == experience_id,
            ExperienceReview.is_synthetic.is_(False),
        )
        return int((await self._session.execute(query)).scalar_one())

    async def has_synthetic_reviews(self, experience_id: str) -> bool:
        query = (
            select(ExperienceReview.id)
            .where(
                ExperienceReview.experience_id == experience_id,
                ExperienceReview.is_synthetic == True,  # noqa: E712 - SQLAlchemy comparison
            )
            .limit(1)
        )
        result = (await self._session.execute(query)).scalar_one_or_none()
        return result is not None

    async def next_synthetic_sequence(self, experience_id: str, generation_version: str) -> int:
        """Next free synthetic_sequence for this experience + generation_version,
        so real traveler reviews (generation_version="user") never collide
        with each other on uq_experience_review_synthetic_seq."""
        query = select(func.max(ExperienceReview.synthetic_sequence)).where(
            ExperienceReview.experience_id == experience_id,
            ExperienceReview.generation_version == generation_version,
        )
        current_max = (await self._session.execute(query)).scalar_one_or_none()
        return 0 if current_max is None else current_max + 1

    def add(self, review: ExperienceReview) -> None:
        self._session.add(review)

    def add_all(self, reviews: list[ExperienceReview]) -> None:
        self._session.add_all(reviews)
