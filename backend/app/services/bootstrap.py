"""First-time bootstrap shared by `app.seed` and `app.cli` (H-02).

Single place that knows how to ensure roles/permissions and the initial
superuser. Rules:
- Passwords only via Argon2id, never plaintext.
- Existing users are NEVER modified (no silent escalation): the function
  reports `created=False` and the caller decides.
- Every creation emits an `audit_logs` row (`user.create`, `via` metadata).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import DEFAULT_ROLES, PERMISSIONS
from app.core.security import hash_password
from app.models.user import Permission, Role, User
from app.services import audit as audit_svc

ADMIN_ROLE = "admin"
MIN_PASSWORD_LENGTH = 10


def validate_admin_input(username: str, email: str, password: str) -> None:
    """Raise ValueError with a human message when input is not acceptable."""
    if not username or len(username) < 3:
        raise ValueError("username must be at least 3 characters")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("invalid email address")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")


async def ensure_roles_permissions(session: AsyncSession) -> dict[str, Role]:
    """Idempotent seed of permissions + default roles. Returns roles by name."""
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
    roles: dict[str, Role] = {}
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
        roles[role_name] = role
    await session.flush()
    return roles


async def ensure_superuser(
    session: AsyncSession, *, username: str, email: str, password: str, via: str = "seed"
) -> tuple[User, bool]:
    """Create the initial superuser (with the full `admin` role).

    Returns `(user, created)`. When the username already exists the row is
    returned untouched and `created` is False. Raises ValueError on invalid
    input (validate first with `validate_admin_input` for friendly errors).
    """
    validate_admin_input(username, email, password)
    existing = await session.execute(
        select(User).options(selectinload(User.roles)).where(User.username == username)
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found, False
    roles = await ensure_roles_permissions(session)
    admin_role = roles[ADMIN_ROLE]
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_active=True,
        is_superuser=True,
    )
    user.roles = [admin_role]
    session.add(user)
    await session.flush()
    await audit_svc.record(
        session,
        action="user.create",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        metadata={"username": username, "via": via},
    )
    await session.flush()
    return user, True
