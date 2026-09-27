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
        query = (
            select(ExperienceCategory, Location.latitude, Location.longitude)
            .join(Experience, Experience.category_id == ExperienceCategory.id)
            .join(Location, Experience.location_id == Location.id)
            .where(Experience.status == "active", Experience.is_synthetic.is_(False))
        )
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
        available: dict[str, ExperienceCategory] = {}
        for category, place_lat, place_lng in rows:
            if radius_km is not None and lat is not None and lng is not None:
                if haversine_km(lat, lng, place_lat, place_lng) > radius_km:
                    continue
            available[category.id] = category
        return sorted(available.values(), key=lambda category: (category.sort_order, category.name))
