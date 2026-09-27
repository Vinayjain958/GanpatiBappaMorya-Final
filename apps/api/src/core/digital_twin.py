"""Process-local TTL storage for short-lived what-if previews."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock

from src.adapters.domain_intelligence import MockDomainIntelligenceProvider
from src.schemas.digital_twin import SimulationResult, WhatIfScenario
from src.services.context_impact import ContextImpactResult

MAX_SIMULATION_SESSIONS = 256
SIMULATION_TTL = timedelta(minutes=15)


@dataclass(frozen=True)
class StoredSimulation:
    owner_id: str
    itinerary_id: str
    itinerary_version: int
    scenario: WhatIfScenario
    result: SimulationResult
    impact: ContextImpactResult


class SimulationSessionStore:
    """Bounded in-memory store; previews are intentionally not persisted."""

    def __init__(self) -> None:
        self._items: dict[str, StoredSimulation] = {}
        self._lock = RLock()

    def put(self, value: StoredSimulation) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._purge(now)
            if len(self._items) >= MAX_SIMULATION_SESSIONS:
                oldest = min(self._items, key=lambda key: self._items[key].result.created_at)
                del self._items[oldest]
            self._items[value.result.simulation_id] = value

    def get(self, simulation_id: str) -> StoredSimulation | None:
        now = datetime.now(UTC)
        with self._lock:
            self._purge(now)
            return self._items.get(simulation_id)

    def remove(self, simulation_id: str) -> None:
        with self._lock:
            self._items.pop(simulation_id, None)

    def _purge(self, now: datetime) -> None:
        expired = [key for key, value in self._items.items() if value.result.expires_at <= now]
        for key in expired:
            del self._items[key]


simulation_session_store = SimulationSessionStore()
_mock_domain_intelligence = MockDomainIntelligenceProvider()


def get_domain_intelligence_provider() -> MockDomainIntelligenceProvider:
    """Default Task 4 implementation; future providers plug in at this boundary."""
    return _mock_domain_intelligence


__all__ = [
    "MAX_SIMULATION_SESSIONS",
    "SIMULATION_TTL",
    "SimulationSessionStore",
    "StoredSimulation",
    "get_domain_intelligence_provider",
    "simulation_session_store",
]
