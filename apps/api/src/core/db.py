"""Async SQLAlchemy engine and session factory.

SQLite (aiosqlite) is used in local development; PostgreSQL (asyncpg) in
production — only DATABASE_URL changes. No SQLite-specific SQL or types
are used anywhere in src/models. See docs/DECISIONS.md ADR-003/ADR-005/ADR-006.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine() -> AsyncEngine:
    settings = get_settings()
    connect_args: dict[str, Any] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_async_engine(settings.database_url, echo=False, connect_args=connect_args)


engine = _make_engine()
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
