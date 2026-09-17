"""Alembic environment (async engine, autogenerate from Base.metadata)."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine

import app.models.device  # noqa: F401
import app.models.hr  # noqa: F401

# Import all models so metadata is complete.
import app.models.user  # noqa: F401
from alembic import context
from app.core.config import get_settings
from app.models.base import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return os.environ.get("DATABASE_URL", get_settings().database_url)


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_async_engine(_url())

    def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    async def _run() -> None:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(_run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
