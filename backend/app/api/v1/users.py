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
from app.models.hr import Company, CorporateGroup
from app.models.user import Role, User
from app.services import access as access_svc
from app.services import audit as audit_svc

router = APIRouter(prefix="/users", tags=["users"])

MIN_PASSWORD_LENGTH = 15


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    is_superuser: bool = False
    role_names: list[str] = Field(default_factory=list)
    corporate_group_ids: list[uuid.UUID] = Field(default_factory=list)
    company_ids: list[uuid.UUID] = Field(default_factory=list)


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, min_length=MIN_PASSWORD_LENGTH, max_length=256)
    is_active: bool | None = None
    is_superuser: bool | None = None
    role_names: list[str] | None = None
    corporate_group_ids: list[uuid.UUID] | None = None
    company_ids: list[uuid.UUID] | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool
    is_superuser: bool
    roles: list[str] = Field(default_factory=list)
    corporate_group_ids: list[uuid.UUID] = Field(default_factory=list)
    company_ids: list[uuid.UUID] = Field(default_factory=list)
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
        corporate_group_ids=sorted((row.id for row in user.corporate_group_scopes), key=str),
        company_ids=sorted((row.id for row in user.company_scopes), key=str),
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
    )


def _validate_email(email: str) -> str:
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Invalid email address")
    return email


async def _get_with_roles(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles))
        .options(
            selectinload(User.corporate_group_scopes),
            selectinload(User.company_scopes),
        )
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


async def _resolve_scopes(
    session: AsyncSession,
    caller: User,
    group_ids: list[uuid.UUID],
    company_ids: list[uuid.UUID],
) -> tuple[list[CorporateGroup], list[Company]]:
    requested_groups = set(group_ids)
    requested_companies = set(company_ids)
    groups = (
        list(
            (
                await session.execute(
                    select(CorporateGroup).where(CorporateGroup.id.in_(requested_groups))
                )
            ).scalars()
        )
        if requested_groups
        else []
    )
    companies = (
        list(
            (
                await session.execute(select(Company).where(Company.id.in_(requested_companies)))
            ).scalars()
        )
        if requested_companies
        else []
    )
    if {row.id for row in groups} != requested_groups:
        raise HTTPException(status_code=422, detail="Unknown corporate group scope")
    if {row.id for row in companies} != requested_companies:
        raise HTTPException(status_code=422, detail="Unknown company scope")
    if not caller.is_superuser:
        # A company-only manager can see its parent group for navigation, but
        # cannot delegate authority over sibling companies in that group.
        if not requested_groups <= await access_svc.direct_group_ids(session, caller):
            raise HTTPException(
                status_code=403, detail="Cannot grant a corporate group outside your scope"
            )
        if not requested_companies <= await access_svc.company_ids(session, caller):
            raise HTTPException(status_code=403, detail="Cannot grant a company outside your scope")
    return groups, companies


async def _ensure_roles_grantable(session: AsyncSession, caller: User, roles: list[Role]) -> None:
    if caller.is_superuser or not roles:
        return
    from app.models.user import Permission, role_permissions
    from app.services import auth as auth_svc

    allowed = await auth_svc.user_permissions(session, caller)
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


async def _active_superuser_count(session: AsyncSession, exclude: uuid.UUID | None = None) -> int:
    query = select(func.count()).select_from(User).where(User.is_superuser, User.is_active)
    if exclude is not None:
        query = query.where(User.id != exclude)
    return int(await session.scalar(query) or 0)


def _forbid_self_target(caller: User, target: User, action: str) -> None:
    if caller.id == target.id:
        raise HTTPException(status_code=403, detail=f"Cannot {action} your own account")


async def _can_manage_user(session: AsyncSession, caller: User, target: User) -> bool:
    if caller.is_superuser:
        return True
    if caller.id == target.id:
        return True
    if target.is_superuser:
        return False
    target_groups = {row.id for row in target.corporate_group_scopes}
    target_companies = {row.id for row in target.company_scopes}
    if not target_groups and not target_companies:
        return False
    return target_groups <= await access_svc.direct_group_ids(
        session, caller
    ) and target_companies <= await access_svc.company_ids(session, caller)


async def _require_manage_user(session: AsyncSession, caller: User, target: User) -> None:
    if not await _can_manage_user(session, caller, target):
        raise HTTPException(status_code=404, detail="User not found")


@router.get("", response_model=list[UserOut])
async def list_users(
    caller: User = Depends(deps.require_permission("users.read")),
    session: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    result = await session.execute(
        select(User)
        .options(
            selectinload(User.roles),
            selectinload(User.corporate_group_scopes),
            selectinload(User.company_scopes),
        )
        .order_by(User.username)
        .limit(200)
    )
    rows = list(result.scalars().all())
    return [_to_out(row) for row in rows if await _can_manage_user(session, caller, row)]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    caller: User = Depends(deps.require_permission("users.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> UserOut:
    _validate_email(payload.email)
    if payload.is_superuser and not caller.is_superuser:
        raise HTTPException(status_code=403, detail="Only superusers can create superusers")
    roles = await _resolve_roles(session, payload.role_names)
    groups, companies = await _resolve_scopes(
        session, caller, payload.corporate_group_ids, payload.company_ids
    )
    await _ensure_roles_grantable(session, caller, roles)
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
    user.corporate_group_scopes = groups
    user.company_scopes = companies
    session.add(user)
    await session.flush()
    await audit_svc.record(
        session,
        action="user.create",
        user_id=caller.id,
        resource_type="user",
        resource_id=user.id,
        request_id=rid,
        metadata={
            "username": user.username,
            "corporate_group_ids": [str(value) for value in payload.corporate_group_ids],
            "company_ids": [str(value) for value in payload.company_ids],
        },
    )
    await session.commit()
    created = await _get_with_roles(session, user.id)
    if created is None:
        raise HTTPException(status_code=500, detail="User creation failed")
    return _to_out(created)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    caller: User = Depends(deps.require_permission("users.read")),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await _get_with_roles(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await _require_manage_user(session, caller, user)
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
    await _require_manage_user(session, caller, user)
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
        _forbid_self_target(caller, user, "disable")
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
        _forbid_self_target(caller, user, "change roles for")
        roles = await _resolve_roles(session, payload.role_names)
        await _ensure_roles_grantable(session, caller, roles)
        user.roles = roles
        changes["roles"] = payload.role_names
    if payload.corporate_group_ids is not None or payload.company_ids is not None:
        _forbid_self_target(caller, user, "change scopes for")
        group_ids = payload.corporate_group_ids
        if group_ids is None:
            group_ids = [row.id for row in user.corporate_group_scopes]
        company_ids = payload.company_ids
        if company_ids is None:
            company_ids = [row.id for row in user.company_scopes]
        groups, companies = await _resolve_scopes(session, caller, group_ids, company_ids)
        user.corporate_group_scopes = groups
        user.company_scopes = companies
        changes["corporate_group_ids"] = [str(value) for value in group_ids]
        changes["company_ids"] = [str(value) for value in company_ids]
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
    await _require_manage_user(session, caller, user)
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
