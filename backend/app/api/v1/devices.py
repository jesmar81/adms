"""Devices admin endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adms.commands import (
    CommandType,
    build_command,
    is_security_push_device,
    require_validated_user_command_profile,
)
from app.api.v1 import deps
from app.api.v1.schemas import CommandIn, CommandOut, DeviceCreate, DeviceOut, DevicePatch
from app.core.config import get_settings
from app.core.database import get_db
from app.models.device import AdmsPayload, Device, DeviceCommand, DeviceEvent
from app.models.user import User
from app.services import access as access_svc
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
        site_id=device.site_id,
        timezone=device.timezone,
        status=device.status,
        derived_status=device_svc.derived_status(device),
        last_activity_at=device.last_activity_at,
        options=device.options or {},
    )


@router.post("", response_model=DeviceOut, status_code=201)
async def create_device(
    payload: DeviceCreate,
    user: User = Depends(deps.require_permission("devices.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> DeviceOut:
    """Provision a serial number before accepting unauthenticated ADMS traffic."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(payload.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail=f"Invalid timezone: {payload.timezone}"
        ) from exc
    if payload.site_id is not None:
        await access_svc.require_site(session, user, payload.site_id)
    elif not user.is_superuser:
        raise HTTPException(status_code=422, detail="A scoped user must assign a branch")
    existing = await device_svc.get_by_serial(session, payload.serial_number)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Serial number already provisioned")
    try:
        device, created = await device_svc.register_device(session, payload.serial_number)
    except Exception:
        await session.rollback()
        raise
    if not created:
        raise HTTPException(status_code=409, detail="Serial number already provisioned")
    device.name = payload.name
    device.model = payload.model
    device.timezone = payload.timezone
    device.site_id = payload.site_id
    # Provisioning is not device activity; it becomes online only when the
    # physical terminal establishes a real ADMS connection.
    device.last_activity_at = None
    await audit_svc.record(
        session,
        action="device.provision",
        user_id=user.id,
        resource_type="device",
        resource_id=device.id,
        device_id=device.id,
        request_id=rid,
        metadata={
            "serial_number": device.serial_number,
            "site_id": str(device.site_id) if device.site_id else None,
        },
    )
    await session.commit()
    return _to_out(device)


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user: User = Depends(deps.require_permission("devices.read")),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceOut]:
    query = (
        select(Device)
        .where(Device.id.in_(await access_svc.device_ids(session, user)))
        .order_by(Device.serial_number)
        .limit(limit)
        .offset(offset)
    )
    if status:
        query = query.where(Device.status == status)
    result = await session.execute(query)
    return [_to_out(d) for d in result.scalars().all()]


@router.get("/{device_id:uuid}", response_model=DeviceOut)
async def get_device(
    device_id: uuid.UUID,
    user: User = Depends(deps.require_permission("devices.read")),
    session: AsyncSession = Depends(get_db),
) -> DeviceOut:
    device = await access_svc.require_device(session, user, device_id)
    return _to_out(device)


@router.patch("/{device_id:uuid}", response_model=DeviceOut)
async def patch_device(
    device_id: uuid.UUID,
    payload: DevicePatch,
    user: User = Depends(deps.require_permission("devices.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> DeviceOut:
    """Update name/model/timezone/status (M-02; `active` clears `disabled`)."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    device = await access_svc.require_device(session, user, device_id)
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
    if payload.site_id is not None:
        await access_svc.require_site(session, user, payload.site_id)
        device.site_id = payload.site_id
        changes["site_id"] = str(payload.site_id)
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


@router.patch("/{device_id:uuid}/disable", response_model=DeviceOut)
async def disable_device(
    device_id: uuid.UUID,
    user: User = Depends(deps.require_permission("devices.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> DeviceOut:
    device = await access_svc.require_device(session, user, device_id)
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


@router.get("/{device_id:uuid}/events")
async def device_events(
    device_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    user: User = Depends(deps.require_permission("devices.read")),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    await access_svc.require_device(session, user, device_id)
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


@router.get("/{device_id:uuid}/capabilities")
async def device_capabilities(
    device_id: uuid.UUID,
    user: User = Depends(deps.require_permission("devices.read")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return evidence-based operations, never guessed firmware support."""
    device = await access_svc.require_device(session, user, device_id)
    payload_types = set(
        (
            await session.execute(
                select(AdmsPayload.data_type)
                .where(AdmsPayload.device_id == device.id, AdmsPayload.data_type.is_not(None))
                .distinct()
            )
        ).scalars()
    )
    confirmed_info = bool(
        await session.scalar(
            select(func.count())
            .select_from(DeviceCommand)
            .where(
                DeviceCommand.device_id == device.id,
                DeviceCommand.command_type == CommandType.INFO.value,
                DeviceCommand.status == "confirmed",
                DeviceCommand.return_code == 0,
            )
        )
    )
    security_push = is_security_push_device(device)
    querydata_user_types = {
        "QUERYDATA:user",
        "QUERYDATA:users",
        "QUERYDATA:userinfo",
    }
    querydata_user_seen = any(item in payload_types for item in querydata_user_types)
    allow_unvalidated = get_settings().zkteco_allow_unvalidated_user_commands
    user_writes_allowed = not security_push or allow_unvalidated
    # Inventory is a read-only probe needed to validate the actual Security
    # PUSH response. Never couple it to the opt-in that enables user writes.
    safe_commands = ["INFO", "CHECK", "LOG", "GET_OPTION", "QUERY_USERINFO"]
    if user_writes_allowed:
        safe_commands.extend(["UPDATE_USERINFO", "DELETE_USERINFO"])
    return {
        "profile": "security_push_acc" if security_push else "legacy_adms",
        "firmware": device.firmware_version,
        "confirmed": {
            "realtime_attendance": "RTLOG" in payload_types,
            "realtime_state": "RTSTATE" in payload_types,
            "command_poll": device.last_command_poll_at is not None,
            "info_command": confirmed_info,
            "user_querydata_received": querydata_user_seen,
        },
        "safe_commands": safe_commands,
        "blocked_operations": (
            []
            if user_writes_allowed
            else ["user_create", "user_update", "user_delete"]
        ),
        "next_validation": (
            "Activa temporalmente ZKTECO_ALLOW_UNVALIDATED_USER_COMMANDS durante una "
            "captura supervisada y usa exclusivamente un PIN de laboratorio."
            if security_push and not querydata_user_seen and allow_unvalidated
            else (
                "Lectura de usuarios observada. Altas, cambios y bajas siguen "
                "bloqueados hasta validar sus comandos por separado."
                if querydata_user_seen
                else "Consulta de inventario habilitada (sólo lectura): solicita usuarios "
                "desde la aplicación y captura la respuesta real del reloj. "
                "Altas, cambios y bajas permanecen bloqueados."
            )
            if security_push
            else None
        ),
    }


@router.post("/{device_id:uuid}/commands", response_model=CommandOut, status_code=201)
async def queue_command(
    device_id: uuid.UUID,
    payload: CommandIn,
    user: User = Depends(deps.require_permission("commands.execute")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> CommandOut:
    device = await access_svc.require_device(session, user, device_id)
    try:
        ctype, wire = build_command(payload.command_type, payload.params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    require_validated_user_command_profile(device, ctype)
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


@router.get("/{device_id:uuid}/commands", response_model=list[CommandOut])
async def list_commands(
    device_id: uuid.UUID,
    user: User = Depends(deps.require_permission("commands.read")),
    session: AsyncSession = Depends(get_db),
) -> list[CommandOut]:
    await access_svc.require_device(session, user, device_id)
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
    user: User = Depends(deps.require_permission("devices.read")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    from datetime import timedelta

    from app.core.config import get_settings

    now = datetime.now(UTC)
    threshold = now - timedelta(seconds=get_settings().zkteco_online_threshold)
    allowed = await access_svc.device_ids(session, user)
    total = (
        await session.scalar(select(func.count()).select_from(Device).where(Device.id.in_(allowed)))
        or 0
    )
    online = (
        await session.scalar(
            select(func.count())
            .select_from(Device)
            .where(Device.id.in_(allowed), Device.last_activity_at >= threshold)
        )
        or 0
    )
    pending = (
        await session.scalar(
            select(func.count())
            .select_from(DeviceCommand)
            .where(DeviceCommand.device_id.in_(allowed), DeviceCommand.status == "pending")
        )
        or 0
    )
    failed = (
        await session.scalar(
            select(func.count())
            .select_from(DeviceCommand)
            .where(DeviceCommand.device_id.in_(allowed), DeviceCommand.status == "failed")
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
