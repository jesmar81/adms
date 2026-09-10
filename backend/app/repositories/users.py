"""users repository — query helpers for the users aggregate."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(
        select(User).where(User.username == username).options(selectinload(User.roles))
    )
    return result.scalar_one_or_none()
