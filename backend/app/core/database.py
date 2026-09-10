"""Async SQLAlchemy engine/session (PostgreSQL+asyncpg prod, SQLite fallback tests)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        kwargs: dict[str, Any] = {"future": True}
        if _is_sqlite(url):
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["pool_size"] = 10
            kwargs["max_overflow"] = 20
        _engine = create_async_engine(url, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    factory = _session_factory
    if factory is None:
        factory = async_sessionmaker(get_engine(), expire_on_commit=False)
        _session_factory = factory
    return factory


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


def reset_engine_for_tests() -> None:
    """Drop cached engine/session factory (tests switch DATABASE_URL)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
