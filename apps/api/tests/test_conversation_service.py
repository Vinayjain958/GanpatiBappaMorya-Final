from __future__ import annotations

import asyncio

from src.adapters.ai import MockAIAdapter
from src.core.config import Settings
from src.models.conversation_session import ConversationSession
from src.schemas.conversation import SearchExperiencesArgs
from src.services.ai_tools import execute_search_experiences
from src.services.conversation import handle_text_turn


def _settings() -> Settings:
    return Settings()


def test_execute_search_experiences_uses_discovery_service(session_factory, discovery_dataset) -> None:
    # Phase 6 replaced the pre-Phase-6 keyword hard-filter with semantic
    # ranking (SemanticRetrievalService) — a "food" query now *ranks*
    # food-relevant experiences to the top rather than excluding every
    # non-matching experience from the result set entirely. Assert on the
    # top (most-similar) result's relevance instead of every returned item.
    async def _run() -> None:
        async with session_factory() as session:
            result = await execute_search_experiences(
                session, _settings(), SearchExperiencesArgs(q="food", limit=5)
            )
            assert result.total >= 1
            assert result.items, "expected at least one ranked result"
            top = result.items[0]
            assert (
                "food" in top.title.lower()
                or "food" in top.short_description.lower()
                or "food" in top.category.name.lower()
            )

    asyncio.run(_run())


def test_execute_search_experiences_drops_unknown_category(session_factory, discovery_dataset) -> None:
    async def _run() -> None:
        async with session_factory() as session:
            # An unrecognized category slug must be silently dropped
            # (model output, not user input) rather than 422ing.
            result = await execute_search_experiences(
                session, _settings(), SearchExperiencesArgs(category_slug="not-a-real-category", limit=5)
            )
            assert result.total >= 1  # falls back to unfiltered search

    asyncio.run(_run())


def test_execute_search_experiences_caps_and_marks_truncated(session_factory, discovery_dataset) -> None:
    async def _run() -> None:
        async with session_factory() as session:
            result = await execute_search_experiences(session, _settings(), SearchExperiencesArgs(limit=1))
            assert len(result.items) == 1
            if result.total > 1:
                assert result.truncated is True

    asyncio.run(_run())


def test_handle_text_turn_end_to_end_with_mock_adapter(session_factory, discovery_dataset) -> None:
    async def _run() -> None:
        async with session_factory() as session:
            conversation = ConversationSession(user_id="test-user-id", mode="text")
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

            response = await handle_text_turn(
                session, MockAIAdapter(), _settings(), conversation, "I want cheap local food near Fort"
            )

            assert response.assistant_text
            assert response.traveler_context.raw_query == "I want cheap local food near Fort"
            assert response.tool_results is not None
            assert conversation.latest_traveler_context is not None

    asyncio.run(_run())


def test_handle_text_turn_bounds_history_window(session_factory, discovery_dataset) -> None:
    async def _run() -> None:
        async with session_factory() as session:
            settings = Settings(conversation_history_window=2)
            conversation = ConversationSession(user_id="test-user-id", mode="text")
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

            for i in range(5):
                await handle_text_turn(session, MockAIAdapter(), settings, conversation, f"message {i}")

            await session.refresh(conversation, attribute_names=["messages"])
            # 5 turns * 2 messages (user + assistant) each = 10 rows persisted,
            # even though only a bounded window was sent to the model.
            assert len(conversation.messages) == 10

    asyncio.run(_run())
