"""check_feasibility tool tests (Phase 6) — real verdict from a real
experience_id, 404 on unknown id, validation error on malformed context,
and proof that a fabricated price/hours field in the tool call has no
effect (CheckFeasibilityArgs has no such fields; DB facts always win)."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from src.adapters.routing import MockRoutingAdapter
from src.core.config import Settings
from src.core.errors import ApiError
from src.schemas.conversation import CheckFeasibilityArgs
from src.services import ai_tools


def test_check_feasibility_real_verdict(session_factory, seeded_ids):
    async def _run():
        async with session_factory() as session:
            args = CheckFeasibilityArgs(experience_id=seeded_ids["experience_id"], budget_max=1000)
            return await ai_tools.execute_check_feasibility(session, MockRoutingAdapter(), Settings(), args)

    verdict = asyncio.run(_run())
    assert verdict.experience_id == seeded_ids["experience_id"]
    assert verdict.status in ("FEASIBLE", "INFEASIBLE", "UNKNOWN")


def test_check_feasibility_unknown_experience_id_raises_404(session_factory, seeded_ids):
    async def _run():
        async with session_factory() as session:
            args = CheckFeasibilityArgs(experience_id="does-not-exist")
            return await ai_tools.execute_check_feasibility(session, MockRoutingAdapter(), Settings(), args)

    with pytest.raises(ApiError) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 404


def test_check_feasibility_malformed_context_raises_validation_error():
    with pytest.raises(ValidationError):
        CheckFeasibilityArgs(experience_id="x", budget_max=-100)  # negative budget rejected


def test_check_feasibility_ignores_invented_price_field(session_factory, seeded_ids):
    """CheckFeasibilityArgs has no `price`/`opening_hours`/`capacity` field
    at all — extra="forbid" means Gemini attempting to smuggle one in via
    the tool call raises validation error rather than silently being
    accepted and influencing the verdict. DB facts are the only source."""
    with pytest.raises(ValidationError):
        CheckFeasibilityArgs.model_validate(
            {"experience_id": seeded_ids["experience_id"], "price": 1.0, "opening_hours": "always open"}
        )


def test_check_feasibility_verdict_uses_db_price_not_any_client_hint(session_factory, seeded_ids):
    """Even a legitimate constraint field (budget_max) only ever gates
    against the DB-stored price — never a client-supplied price."""

    async def _run():
        async with session_factory() as session:
            args = CheckFeasibilityArgs(experience_id=seeded_ids["experience_id"], budget_max=1)
            return await ai_tools.execute_check_feasibility(session, MockRoutingAdapter(), Settings(), args)

    verdict = asyncio.run(_run())
    # Seeded experience has minimum_price=100/maximum_price=500 -> budget_max=1 must fail.
    assert verdict.status == "INFEASIBLE"
    assert any(r.code.value == "BUDGET_EXCEEDED" for r in verdict.reasons)
