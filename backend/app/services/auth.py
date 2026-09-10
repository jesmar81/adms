"""Admin auth service: users, Argon2id verify, token pair issue, audit hooks."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import security
from app.core.exceptions import AuthError
from app.models.user import User


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(
        select(User).where(User.username == username).options(selectinload(User.roles))
    )
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    result = await session.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    return result.scalar_one_or_none()


async def authenticate(session: AsyncSession, username: str, password: str) -> User:
    user = await get_user_by_username(session, username)
    if user is None or not user.is_active:
        raise AuthError("Invalid credentials")
    if not security.verify_password(password, user.password_hash):
        raise AuthError("Invalid credentials")
    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return user


async def user_permissions(session: AsyncSession, user: User) -> set[str]:
    if user.is_superuser:
        from app.core.constants import PERMISSIONS

        return set(PERMISSIONS)
    from sqlalchemy import select as sa_select

    from app.models.user import Permission, Role, role_permissions, user_roles

    stmt = (
        sa_select(Permission.code)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .join(Role, Role.id == role_permissions.c.role_id)
        .join(user_roles, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user.id)
    )
    result = await session.execute(stmt)
    return set(result.scalars().all())
