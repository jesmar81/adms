"""Devices admin endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adms.commands import CommandType, build_command
from app.api.v1 import deps
from app.api.v1.schemas import CommandIn, CommandOut, DeviceOut, DevicePatch
from app.core.database import get_db
from app.models.device import Device, DeviceCommand, DeviceEvent
from app.models.user import User
from app.services import audit as audit_svc
from app.services import command as command_svc
from app.services import device as device_svc

router = APIRouter(prefix="/devices", tags=["devices"])


def _to_out(device: Device) -> DeviceOut:
    return DeviceOut(
        id=device.id,
        serial_number=device.serial_number,
        name=device.name,
        model=device.model,
        firmware_version=device.firmware_version,
        platform=device.platform,
        # PostgreSQL INET returns ipaddress.IPv4Address/IPv6Address objects
        # via asyncpg; DeviceOut expects str. str() is idempotent for str.
        ip_address=str(device.ip_address) if device.ip_address is not None else None,
        mac_address=device.mac_address,
        timezone=device.timezone,
        status=device.status,
        derived_status=device_svc.derived_status(device),
        last_activity_at=device.last_activity_at,
        options=device.options or {},
    )


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    _user: User = Depends(deps.require_permission("devices.read")),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceOut]:
    query = select(Device).order_by(Device.serial_number).limit(limit).offset(offset)
    if status:
        query = query.where(Device.status == status)
    result = await session.execute(query)
    return [_to_out(d) for d in result.scalars().all()]


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: uuid.UUID,
    _user: User = Depends(deps.require_permission("devices.read")),
    session: AsyncSession = Depends(get_db),
) -> DeviceOut:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return _to_out(device)


@router.patch("/{device_id}", response_model=DeviceOut)
async def patch_device(
    device_id: uuid.UUID,
    payload: DevicePatch,
    user: User = Depends(deps.require_permission("devices.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> DeviceOut:
    """Update name/model/timezone/status (M-02; `active` clears `disabled`)."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    changes: dict[str, object] = {}
    if payload.name is not None:
        device.name = payload.name
        changes["name"] = payload.name
    if payload.model is not None:
        device.model = payload.model
        changes["model"] = payload.model
    if payload.timezone is not None:
        try:
            ZoneInfo(payload.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid timezone: {payload.timezone}"
            ) from exc
        device.timezone = payload.timezone
        changes["timezone"] = payload.timezone
    if payload.status is not None:
        device.status = "disabled" if payload.status == "disabled" else "unknown"
        changes["status"] = device.status
    if changes:
        await audit_svc.record(
            session,
            action="device.update",
            user_id=user.id,
            resource_type="device",
            resource_id=device.id,
            device_id=device.id,
            request_id=rid,
            metadata=changes,
        )
        await session.commit()
    return _to_out(device)


@router.patch("/{device_id}/disable", response_model=DeviceOut)
async def disable_device(
    device_id: uuid.UUID,
    user: User = Depends(deps.require_permission("devices.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> DeviceOut:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    device.status = "disabled"
    await audit_svc.record(
        session,
        action="device.update",
        user_id=user.id,
        resource_type="device",
        resource_id=device.id,
        device_id=device.id,
        request_id=rid,
        metadata={"status": "disabled"},
    )
    await session.commit()
    return _to_out(device)


@router.get("/{device_id}/events")
async def device_events(
    device_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    _user: User = Depends(deps.require_permission("devices.read")),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(DeviceEvent)
        .where(DeviceEvent.device_id == device_id)
        .order_by(DeviceEvent.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "type": e.event_type,
            "severity": e.severity,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in result.scalars().all()
    ]


@router.post("/{device_id}/commands", response_model=CommandOut, status_code=201)
async def queue_command(
    device_id: uuid.UUID,
    payload: CommandIn,
    user: User = Depends(deps.require_permission("commands.execute")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> CommandOut:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    try:
        ctype, wire = build_command(payload.command_type, payload.params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = await command_svc.queue_command(
        session,
        serial=device.serial_number,
        command_type=CommandType(ctype),
        command=wire,
        created_by=user.id,
    )
    await audit_svc.record(
        session,
        action="device.command",
        user_id=user.id,
        resource_type="device_command",
        resource_id=row.id,
        device_id=device.id,
        request_id=rid,
        metadata={"command_type": payload.command_type},
    )
    await session.commit()
    return CommandOut(
        id=row.id,
        device_id=row.device_id,
        protocol_command_id=row.protocol_command_id,
        command_type=row.command_type,
        command=row.command,
        status=row.status,
        return_code=row.return_code,
        queued_at=row.queued_at,
        sent_at=row.sent_at,
        confirmed_at=row.confirmed_at,
    )


@router.get("/{device_id}/commands", response_model=list[CommandOut])
async def list_commands(
    device_id: uuid.UUID,
    _user: User = Depends(deps.require_permission("commands.read")),
    session: AsyncSession = Depends(get_db),
) -> list[CommandOut]:
    result = await session.execute(
        select(DeviceCommand)
        .where(DeviceCommand.device_id == device_id)
        .order_by(DeviceCommand.protocol_command_id.desc())
        .limit(100)
    )
    return [
        CommandOut(
            id=r.id,
            device_id=r.device_id,
            protocol_command_id=r.protocol_command_id,
            command_type=r.command_type,
            command=r.command,
            status=r.status,
            return_code=r.return_code,
            queued_at=r.queued_at,
            sent_at=r.sent_at,
            confirmed_at=r.confirmed_at,
        )
        for r in result.scalars().all()
    ]


@router.get("/stats/summary")
async def summary(
    _user: User = Depends(deps.require_permission("devices.read")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    from datetime import timedelta

    from app.core.config import get_settings

    now = datetime.now(UTC)
    threshold = now - timedelta(seconds=get_settings().zkteco_online_threshold)
    total = await session.scalar(select(func.count()).select_from(Device)) or 0
    online = (
        await session.scalar(
            select(func.count()).select_from(Device).where(Device.last_activity_at >= threshold)
        )
        or 0
    )
    pending = (
        await session.scalar(
            select(func.count()).select_from(DeviceCommand).where(DeviceCommand.status == "pending")
        )
        or 0
    )
    failed = (
        await session.scalar(
            select(func.count()).select_from(DeviceCommand).where(DeviceCommand.status == "failed")
        )
        or 0
    )
    return {
        "total": total,
        "online": online,
        "offline": total - online,
        "pending_commands": pending,
        "failed_commands": failed,
    }
