"""Extension boundary for later domain intelligence work (Task 5).

Task 4 ships only a transparent mock provider. No Nugen client, data source,
or decision authority is introduced here.
"""

from __future__ import annotations

from typing import Protocol

from src.schemas.domain_intelligence import DomainIntelligenceInput, DomainIntelligenceResult


class DomainIntelligenceProvider(Protocol):
    async def summarize(self, facts: DomainIntelligenceInput) -> DomainIntelligenceResult: ...


class MockDomainIntelligenceProvider:
    async def summarize(self, facts: DomainIntelligenceInput) -> DomainIntelligenceResult:
        categories = ", ".join(sorted(set(facts.impact_categories))) or "no material impact categories"
        return DomainIntelligenceResult(
            summary=f"Scenario preview considered {categories}.",
            notes=["This mock summary does not make feasibility or safety decisions."],
        )


__all__ = ["DomainIntelligenceProvider", "MockDomainIntelligenceProvider"]
