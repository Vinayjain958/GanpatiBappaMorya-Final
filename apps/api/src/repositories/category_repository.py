from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.category import ExperienceCategory
from src.models.experience import Experience
from src.models.location import Location
from src.core.geo import bounding_box, haversine_km


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[ExperienceCategory]:
        query = select(ExperienceCategory).order_by(ExperienceCategory.sort_order)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> ExperienceCategory | None:
        query = select(ExperienceCategory).where(ExperienceCategory.slug == slug)
        result = await self._session.execute(query)
        return result.scalars().one_or_none()

    async def get_by_id(self, category_id: str) -> ExperienceCategory | None:
        return await self._session.get(ExperienceCategory, category_id)

    async def list_available(
        self,
        *,
        city: str | None = None,
        locality: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        radius_km: float | None = None,
    ) -> list[ExperienceCategory]:
        """Return categories with active, non-synthetic places in an area."""
        radius_filter = lat is not None and lng is not None and radius_km is not None
        # Only the category id (plus coordinates when a radius must be checked
        # exactly) is fetched per place; without a radius the database returns
        # just the distinct ids. Full category rows are loaded once at the end.
        columns = (
            (Experience.category_id, Location.latitude, Location.longitude)
            if radius_filter
            else (Experience.category_id,)
        )
        query = (
            select(*columns)
            .join(Location, Experience.location_id == Location.id)
            .where(Experience.status == "active", Experience.is_synthetic.is_(False))
        )
        if not radius_filter:
            query = query.distinct()
        if city:
            query = query.where(Location.city == city)
        if locality:
            query = query.where(Location.locality == locality)
        bounds = None
        if lat is not None and lng is not None and radius_km is not None:
            bounds = bounding_box(lat, lng, radius_km)
            query = query.where(
                Location.latitude >= bounds.min_lat,
                Location.latitude <= bounds.max_lat,
                Location.longitude >= bounds.min_lng,
                Location.longitude <= bounds.max_lng,
            )

        rows = (await self._session.execute(query)).all()
        category_ids: set[str] = set()
        for row in rows:
            if radius_filter:
                category_id, place_lat, place_lng = row
                if haversine_km(lat, lng, place_lat, place_lng) > radius_km:  # type: ignore[arg-type]
                    continue
            else:
                (category_id,) = row
            category_ids.add(category_id)
        if not category_ids:
            return []
        categories = (
            await self._session.execute(
                select(ExperienceCategory).where(ExperienceCategory.id.in_(category_ids))
            )
        ).scalars().all()
        return sorted(categories, key=lambda category: (category.sort_order, category.name))
