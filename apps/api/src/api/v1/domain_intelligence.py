"""Safe configuration diagnostic for optional domain intelligence."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.core.config import Settings, get_settings

router = APIRouter(prefix="/domain-intelligence", tags=["domain-intelligence"])


class DomainIntelligenceHealth(BaseModel):
    configured: bool
    model_id: str | None


@router.get("/health", response_model=DomainIntelligenceHealth)
async def get_domain_intelligence_health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DomainIntelligenceHealth:
    return DomainIntelligenceHealth(
        configured=settings.nugen_enabled,
        model_id=settings.nugen_model_id if settings.nugen_enabled else None,
    )


__all__ = ["router"]
