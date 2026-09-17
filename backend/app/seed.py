"""Seed initial roles + permissions (§98) and, optionally, the first admin.

Set ZKTECO_ADMIN_USERNAME / ZKTECO_ADMIN_EMAIL / ZKTECO_ADMIN_PASSWORD to
also bootstrap the initial superuser (idempotent: an existing username is
left untouched). No fake devices. Schema must come from Alembic in
production; the local create_all below is a dev/test convenience only.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.device  # noqa: F401
import app.models.hr  # noqa: F401
from app.core.config import get_settings
from app.models.base import Base
from app.services.bootstrap import ensure_roles_permissions, ensure_superuser


async def main() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await ensure_roles_permissions(session)
        await session.commit()
    print("seeded roles+permissions")
    username = os.environ.get("ZKTECO_ADMIN_USERNAME", "")
    email = os.environ.get("ZKTECO_ADMIN_EMAIL", "")
    password = os.environ.get("ZKTECO_ADMIN_PASSWORD", "")
    if not username and not email and not password:
        print("hint: set ZKTECO_ADMIN_USERNAME/EMAIL/PASSWORD to bootstrap the first admin,")
        print("      or run: python -m app.cli createsuperuser")
        await engine.dispose()
        return
    async with factory() as session:
        try:
            user, created = await ensure_superuser(
                session, username=username, email=email, password=password, via="seed"
            )
        except ValueError as exc:
            print(f"error: invalid admin input: {exc}", flush=True)
            await engine.dispose()
            raise SystemExit(2) from exc
        await session.commit()
    await engine.dispose()
    if created:
        print(f"superuser '{user.username}' created")
    else:
        print(f"superuser '{username}' already exists, left untouched")


if __name__ == "__main__":
    asyncio.run(main())
