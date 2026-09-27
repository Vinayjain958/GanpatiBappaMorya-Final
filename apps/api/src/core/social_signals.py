"""Process-level social signal adapter/service wiring."""

from __future__ import annotations

from functools import lru_cache

from src.adapters.social_signals import BlueskySocialSignalAdapter
from src.core.config import get_settings
from src.core.location import get_geocoding_adapter
from src.services.social_signals import SocialSignalService


@lru_cache
def get_social_signal_service() -> SocialSignalService:
    settings = get_settings()
    return SocialSignalService(
        settings=settings,
        geocoder=get_geocoding_adapter(),
        adapter=BlueskySocialSignalAdapter(settings),
    )


__all__ = ["get_social_signal_service"]
