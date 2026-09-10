"""Seed initial roles + permissions only (§98). No fake devices."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

import app.models.device  # noqa: F401
from app.core.config import get_settings
from app.core.constants import DEFAULT_ROLES, PERMISSIONS
from app.models.base import Base
from app.models.user import Permission, Role


async def main() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        for code in PERMISSIONS:
            exists = await session.scalar(select(Permission).where(Permission.code == code))
            if exists is None:
                session.add(
                    Permission(
                        id=uuid.uuid4(),
                        code=code,
                        description=code,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
        await session.flush()
        for role_name, codes in DEFAULT_ROLES.items():
            role = await session.scalar(
                select(Role).options(selectinload(Role.permissions)).where(Role.name == role_name)
            )
            if role is None:
                role = Role(
                    id=uuid.uuid4(),
                    name=role_name,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                session.add(role)
                await session.flush()
                await session.refresh(role, attribute_names=["permissions"])
            result = await session.execute(select(Permission).where(Permission.code.in_(codes)))
            role.permissions = list(result.scalars().all())
        await session.commit()
    print("seeded roles+permissions")


if __name__ == "__main__":
    asyncio.run(main())
