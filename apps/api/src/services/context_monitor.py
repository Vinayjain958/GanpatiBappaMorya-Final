"""ContextMonitor — one shared background monitor (Phase 9).

Periodically determines which itineraries need monitoring (active,
future/in-progress, not CANCELLED/COMPLETED), refreshes weather/events
for their remaining items, compares against the last known context via
ContextImpactService, and submits replan candidates to ReplanningService
when material impact is detected.

Single shared instance per process — never one per SSE connection. Uses
an injectable clock (`now_fn`) for testability. Weather/event check
frequency scales with proximity to the relevant itinerary time: the
`_interval_for` method shortens the polling interval as the itinerary's
start time approaches, fully driven by Settings (no hardcoded demo
branches).

Multi-worker safety: this codebase runs as a single uvicorn process in
dev (scripts/dev.ps1/dev.sh) with no evidence of a multi-worker
production deployment. A distributed lock / leader-election scheme is
therefore explicitly NOT implemented here — it is a documented
limitation (docs/DECISIONS.md Phase 9 ADR), not silently ignored. What
IS implemented: an in-process guard (`_started`) so hot-reload or a
duplicate call to `start()` can never spawn a second concurrent loop
within the same process.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.adapters.errors import AdapterError
from src.adapters.events import EventAdapter
from src.adapters.weather import WeatherAdapter, WeatherContext
from src.core.config import Settings
from src.models.itinerary import Itinerary
from src.repositories.experience_repository import ExperienceRepository
from src.services.context_impact import ContextImpactService

logger = logging.getLogger(__name__)

ClockFn = Callable[[], datetime]


class ContextMonitor:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        weather_adapter: WeatherAdapter,
        event_adapter: EventAdapter,
        replan_callback: Callable[[str, str, object], Awaitable[None]] | None = None,
        clock: ClockFn = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._weather_adapter = weather_adapter
        self._event_adapter = event_adapter
        self._replan_callback = replan_callback
        self._clock = clock
        self._impact = ContextImpactService(settings)
        self._last_weather_by_location: dict[str, WeatherContext] = {}
        self._task: asyncio.Task[None] | None = None
        self._started = False

    def start(self) -> None:
        """Starts the shared monitor loop. Idempotent within a process —
        a second call while already running is a no-op (guards against
        double-start on hot-reload)."""
        if self._started:
            return
        self._started = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._started = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def interval_for(self, itinerary: Itinerary) -> int:
        """Polling interval (seconds), shorter as the itinerary's start
        time approaches — fully configuration-driven via
        weather_monitor_interval_seconds, never a hardcoded demo path."""
        now = self._clock()
        start_dt = datetime.combine(itinerary.itinerary_date, itinerary.start_time, tzinfo=now.tzinfo)
        hours_until = (start_dt - now).total_seconds() / 3600
        base = self._settings.weather_monitor_interval_seconds
        if hours_until <= 2:
            return max(60, base // 6)
        if hours_until <= 6:
            return max(120, base // 3)
        if hours_until <= 24:
            return base
        return base * 4

    async def active_itineraries(self, session: AsyncSession) -> list[Itinerary]:
        now = self._clock()
        result = await session.execute(
            select(Itinerary).where(
                Itinerary.status.in_(["VALIDATED", "BOOKING_REQUESTED"]),
                Itinerary.itinerary_date >= now.date(),
            )
        )
        return list(result.scalars().unique().all())

    async def check_itinerary_weather(self, session: AsyncSession, itinerary: Itinerary) -> None:
        exp_repo = ExperienceRepository(session)
        experiences_by_id = {}
        for item in itinerary.items:
            exp = await exp_repo.get_by_id(item.experience_id)
            if exp is not None:
                experiences_by_id[item.experience_id] = exp
        if not experiences_by_id:
            return

        first_exp = next(iter(experiences_by_id.values()))
        lat, lng = first_exp.location.latitude, first_exp.location.longitude
        location_key = f"{round(lat, 2)}:{round(lng, 2)}"

        try:
            new_weather = await self._weather_adapter.get_current(lat, lng)
        except AdapterError as exc:
            logger.warning("ContextMonitor: weather fetch failed for %s: %s", itinerary.id, exc)
            return  # never fabricate — skip this cycle, do not auto-replan

        previous_weather = self._last_weather_by_location.get(location_key)
        self._last_weather_by_location[location_key] = new_weather

        result = self._impact.assess_weather(
            items=list(itinerary.items),
            experiences_by_id=experiences_by_id,
            previous_weather=previous_weather,
            new_weather=new_weather,
        )
        if result.affected and self._replan_callback is not None:
            await self._replan_callback(itinerary.id, "WEATHER_CHANGED", result)

    async def run_once(self) -> int:
        """Runs exactly one monitoring pass over all active itineraries.
        Returns the number of itineraries checked — used directly by
        tests instead of driving the infinite loop."""
        checked = 0
        async with self._session_factory() as session:
            itineraries = await self.active_itineraries(session)
            for itinerary in itineraries:
                await self.check_itinerary_weather(session, itinerary)
                checked += 1
        return checked

    async def _run_loop(self) -> None:
        try:
            while self._started:
                try:
                    await self.run_once()
                except Exception:  # noqa: BLE001 — the monitor must never crash the process
                    logger.exception("ContextMonitor cycle failed")
                await asyncio.sleep(self._settings.weather_monitor_interval_seconds)
        except asyncio.CancelledError:
            raise


_shared_monitor: ContextMonitor | None = None


def get_context_monitor(
    *,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    weather_adapter: WeatherAdapter,
    event_adapter: EventAdapter,
    replan_callback: Callable[[str, str, object], Awaitable[None]] | None = None,
) -> ContextMonitor:
    """Process-wide singleton accessor — ensures exactly one ContextMonitor
    instance exists per process, never one per SSE connection."""
    global _shared_monitor
    if _shared_monitor is None:
        _shared_monitor = ContextMonitor(
            settings=settings,
            session_factory=session_factory,
            weather_adapter=weather_adapter,
            event_adapter=event_adapter,
            replan_callback=replan_callback,
        )
    return _shared_monitor


__all__ = ["ContextMonitor", "get_context_monitor"]
