"""Business-scope authorization for corporate groups, companies and devices.

RBAC answers *what* an operator may do. These helpers answer *where* they may
do it. Unauthorized rows deliberately look like 404s to avoid tenant
enumeration.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.hr import Company, Employment, Person, Site
from app.models.user import User, user_company_scopes, user_group_scopes


async def direct_group_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    if user.is_superuser:
        from app.models.hr import CorporateGroup

        return set((await session.execute(select(CorporateGroup.id))).scalars())
    return set(
        (
            await session.execute(
                select(user_group_scopes.c.corporate_group_id).where(
                    user_group_scopes.c.user_id == user.id
                )
            )
        ).scalars()
    )


async def group_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    if user.is_superuser:
        from app.models.hr import CorporateGroup

        return set((await session.execute(select(CorporateGroup.id))).scalars())
    direct = await direct_group_ids(session, user)
    via_company = set(
        (
            await session.execute(
                select(Company.corporate_group_id)
                .join(user_company_scopes, user_company_scopes.c.company_id == Company.id)
                .where(user_company_scopes.c.user_id == user.id)
            )
        ).scalars()
    )
    return direct | via_company


async def company_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    if user.is_superuser:
        return set((await session.execute(select(Company.id))).scalars())
    direct = set(
        (
            await session.execute(
                select(user_company_scopes.c.company_id).where(
                    user_company_scopes.c.user_id == user.id
                )
            )
        ).scalars()
    )
    groups = set(
        (
            await session.execute(
                select(user_group_scopes.c.corporate_group_id).where(
                    user_group_scopes.c.user_id == user.id
                )
            )
        ).scalars()
    )
    if groups:
        direct.update(
            (
                await session.execute(
                    select(Company.id).where(Company.corporate_group_id.in_(groups))
                )
            )
            .scalars()
            .all()
        )
    return direct


async def require_group(session: AsyncSession, user: User, group_id: uuid.UUID) -> None:
    if group_id not in await group_ids(session, user):
        raise HTTPException(status_code=404, detail="Corporate group not found")


async def require_group_management(session: AsyncSession, user: User, group_id: uuid.UUID) -> None:
    """Require an explicit whole-group grant (company grants are insufficient)."""
    if user.is_superuser:
        return
    allowed = await direct_group_ids(session, user)
    if group_id not in allowed:
        raise HTTPException(status_code=404, detail="Corporate group not found")


async def require_company(session: AsyncSession, user: User, company_id: uuid.UUID) -> Company:
    if company_id not in await company_ids(session, user):
        raise HTTPException(status_code=404, detail="Company not found")
    row = await session.get(Company, company_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return row


async def require_site(session: AsyncSession, user: User, site_id: uuid.UUID) -> Site:
    row = await session.get(Site, site_id)
    if row is None or row.company_id not in await company_ids(session, user):
        raise HTTPException(status_code=404, detail="Branch not found")
    return row


async def require_person(session: AsyncSession, user: User, person_id: uuid.UUID) -> Person:
    row = await session.get(Person, person_id)
    if row is None or row.id not in await person_ids(session, user):
        raise HTTPException(status_code=404, detail="Person not found")
    return row


async def person_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    """People visible through a whole-group grant or an employment grant.

    Seeing the parent group of an explicitly granted company is useful for
    navigation, but must not expose every worker employed by sibling
    companies in that group.
    """
    if user.is_superuser:
        return set((await session.execute(select(Person.id))).scalars())
    direct_groups = await direct_group_ids(session, user)
    companies = await company_ids(session, user)
    employment_people = select(Employment.person_id).where(Employment.company_id.in_(companies))
    query = select(Person.id).where(
        or_(
            Person.corporate_group_id.in_(direct_groups),
            Person.id.in_(employment_people),
        )
    )
    return set((await session.execute(query)).scalars())


async def require_employment(
    session: AsyncSession, user: User, employment_id: uuid.UUID
) -> Employment:
    row = await session.get(Employment, employment_id)
    if row is None or row.company_id not in await company_ids(session, user):
        raise HTTPException(status_code=404, detail="Employment not found")
    return row


async def require_device(session: AsyncSession, user: User, device_id: uuid.UUID) -> Device:
    row = await session.get(Device, device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if user.is_superuser:
        return row
    if row.site_id is None:
        raise HTTPException(status_code=404, detail="Device not found")
    site = await session.get(Site, row.site_id)
    if site is None or site.company_id not in await company_ids(session, user):
        raise HTTPException(status_code=404, detail="Device not found")
    return row


async def device_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    if user.is_superuser:
        return set((await session.execute(select(Device.id))).scalars())
    companies = await company_ids(session, user)
    if not companies:
        return set()
    return set(
        (
            await session.execute(
                select(Device.id)
                .join(Site, Device.site_id == Site.id)
                .where(Site.company_id.in_(companies))
            )
        ).scalars()
    )
