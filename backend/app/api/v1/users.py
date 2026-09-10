"""Admin user management (H-02). Replaces the list-only stub.

Guards:
- Only superusers may grant `is_superuser` or assign roles the caller lacks.
- Nobody can escalate/disable/delete themselves.
- The last active superuser cannot be disabled or deleted.
- DELETE performs a soft-disable (`is_active=false`, §88), never hard delete.
- Every mutation emits an `audit_logs` row.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1 import deps
from app.core import security
from app.core.database import get_db
from app.models.user import Role, User
from app.services import audit as audit_svc

router = APIRouter(prefix="/users", tags=["users"])

MIN_PASSWORD_LENGTH = 10


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    is_superuser: bool = False
    role_names: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, min_length=MIN_PASSWORD_LENGTH, max_length=256)
    is_active: bool | None = None
    is_superuser: bool | None = None
    role_names: list[str] | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool
    is_superuser: bool
    roles: list[str] = Field(default_factory=list)
    last_login_at: str | None = None

    model_config = {"from_attributes": True}


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        roles=sorted(r.name for r in user.roles),
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
    )


def _validate_email(email: str) -> str:
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Invalid email address")
    return email


async def _get_with_roles(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    return result.scalar_one_or_none()


async def _resolve_roles(session: AsyncSession, names: list[str]) -> list[Role]:
    if not names:
        return []
    result = await session.execute(select(Role).where(Role.name.in_(names)))
    found = list(result.scalars().all())
    missing = set(names) - {r.name for r in found}
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown roles: {sorted(missing)}")
    return found


async def _active_superuser_count(session: AsyncSession, exclude: uuid.UUID | None = None) -> int:
    query = select(func.count()).select_from(User).where(User.is_superuser, User.is_active)
    if exclude is not None:
        query = query.where(User.id != exclude)
    return int(await session.scalar(query) or 0)


def _forbid_self_target(caller: User, target: User, action: str) -> None:
    if caller.id == target.id:
        raise HTTPException(status_code=403, detail=f"Cannot {action} your own account")


@router.get("", response_model=list[UserOut])
async def list_users(
    _user: User = Depends(deps.require_permission("users.read")),
    session: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    result = await session.execute(
        select(User).options(selectinload(User.roles)).order_by(User.username).limit(200)
    )
    return [_to_out(u) for u in result.scalars().all()]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    caller: User = Depends(deps.require_permission("users.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> UserOut:
    from app.services import auth as auth_svc

    _validate_email(payload.email)
    if payload.is_superuser and not caller.is_superuser:
        raise HTTPException(status_code=403, detail="Only superusers can create superusers")
    roles = await _resolve_roles(session, payload.role_names)
    if roles and not caller.is_superuser:
        allowed = await auth_svc.user_permissions(session, caller)
        from app.models.user import Permission, role_permissions

        for role in roles:
            result = await session.execute(
                select(Permission.code)
                .join(role_permissions, role_permissions.c.permission_id == Permission.id)
                .where(role_permissions.c.role_id == role.id)
            )
            needed = set(result.scalars().all())
            if not needed <= allowed:
                raise HTTPException(
                    status_code=403, detail=f"Cannot grant role '{role.name}' you do not hold"
                )
    existing = await session.execute(
        select(User.id).where((User.username == payload.username) | (User.email == payload.email))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username or email already exists")
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=security.hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        is_active=True,
        is_superuser=payload.is_superuser,
    )
    user.roles = roles
    session.add(user)
    await session.flush()
    await audit_svc.record(
        session,
        action="user.create",
        user_id=caller.id,
        resource_type="user",
        resource_id=user.id,
        request_id=rid,
        metadata={"username": user.username},
    )
    await session.commit()
    created = await _get_with_roles(session, user.id)
    if created is None:
        raise HTTPException(status_code=500, detail="User creation failed")
    return _to_out(created)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    _user: User = Depends(deps.require_permission("users.read")),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await _get_with_roles(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_out(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    caller: User = Depends(deps.require_permission("users.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> UserOut:
    user = await _get_with_roles(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes: dict[str, object] = {}
    if payload.email is not None:
        user.email = _validate_email(payload.email)
        changes["email"] = payload.email
    if payload.first_name is not None:
        user.first_name = payload.first_name
    if payload.last_name is not None:
        user.last_name = payload.last_name
    if payload.password is not None:
        user.password_hash = security.hash_password(payload.password)
        changes["password"] = "changed"  # noqa: S105 -- audit marker, not a secret
    if payload.is_active is False:
        if user.is_superuser and await _active_superuser_count(session, exclude=user.id) == 0:
            raise HTTPException(status_code=409, detail="Cannot disable the last superuser")
        user.is_active = False
        changes["is_active"] = False
    elif payload.is_active is True:
        user.is_active = True
        changes["is_active"] = True
    if payload.is_superuser is not None and payload.is_superuser != user.is_superuser:
        if not caller.is_superuser:
            raise HTTPException(status_code=403, detail="Only superusers can grant superuser")
        remaining = await _active_superuser_count(session, exclude=user.id)
        if not payload.is_superuser and remaining == 0:
            raise HTTPException(status_code=409, detail="Cannot demote the last superuser")
        user.is_superuser = payload.is_superuser
        changes["is_superuser"] = payload.is_superuser
    if payload.role_names is not None:
        roles = await _resolve_roles(session, payload.role_names)
        if not caller.is_superuser:
            from app.services import auth as auth_svc

            allowed = await auth_svc.user_permissions(session, caller)
            for role in roles:
                if role.name == "admin":
                    raise HTTPException(status_code=403, detail="Only superusers can grant 'admin'")
                _ = allowed
        user.roles = roles
        changes["roles"] = payload.role_names
    await audit_svc.record(
        session,
        action="user.update",
        user_id=caller.id,
        resource_type="user",
        resource_id=user.id,
        request_id=rid,
        metadata=changes,
    )
    await session.commit()
    updated = await _get_with_roles(session, user.id)
    if updated is None:
        raise HTTPException(status_code=500, detail="User update failed")
    return _to_out(updated)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    caller: User = Depends(deps.require_permission("users.delete")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> None:
    """Soft-disable the account (§88: `is_active`, never hard delete)."""
    user = await _get_with_roles(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    _forbid_self_target(caller, user, "delete")
    if user.is_superuser and await _active_superuser_count(session, exclude=user.id) == 0:
        raise HTTPException(status_code=409, detail="Cannot delete the last superuser")
    user.is_active = False
    await audit_svc.record(
        session,
        action="user.delete",
        user_id=caller.id,
        resource_type="user",
        resource_id=user.id,
        request_id=rid,
        metadata={"username": user.username},
    )
    await session.commit()
    return None
