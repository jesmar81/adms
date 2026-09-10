"""devices repository — query helpers for the devices aggregate."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device


async def get_by_serial(session: AsyncSession, serial: str) -> Device | None:
    result = await session.execute(select(Device).where(Device.serial_number == serial))
    return result.scalar_one_or_none()


async def list_devices(
    session: AsyncSession, *, status: str | None = None, limit: int = 50, offset: int = 0
) -> list[Device]:
    query = select(Device).order_by(Device.serial_number).limit(limit).offset(offset)
    if status:
        query = query.where(Device.status == status)
    result = await session.execute(query)
    return list(result.scalars().all())
