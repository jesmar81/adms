"""Attendance / device-users / users / audit admin endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adms.commands import CommandType
from app.api.v1 import deps
from app.api.v1.schemas import AttendanceOut, DeviceUserIn, DeviceUserOut, DeviceUserUpdate
from app.core.database import get_db
from app.models.device import AttendanceLog, Device, DeviceUser
from app.models.user import AuditLog, User
from app.services import audit as audit_svc
from app.services import command as command_svc

attendance_router = APIRouter(prefix="/attendance", tags=["attendance"])


@attendance_router.get("", response_model=list[AttendanceOut])
async def list_attendance(
    device_id: uuid.UUID | None = None,
    pin: str | None = Query(default=None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: int | None = None,
    verify_mode: int | None = None,
    work_code: str | None = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    _user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> list[AttendanceOut]:
    for label, value in (("date_from", date_from), ("date_to", date_to)):
        if value is not None and value.tzinfo is None:
            raise HTTPException(status_code=422, detail=f"{label} must include a timezone")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be <= date_to")
    query = (
        select(AttendanceLog).order_by(AttendanceLog.recorded_at.desc()).limit(limit).offset(offset)
    )
    if device_id:
        query = query.where(AttendanceLog.device_id == device_id)
    if pin:
        query = query.where(AttendanceLog.device_user_pin == pin)
    if date_from:
        query = query.where(AttendanceLog.recorded_at >= date_from)
    if date_to:
        query = query.where(AttendanceLog.recorded_at <= date_to)
    if status is not None:
        query = query.where(AttendanceLog.status == status)
    if verify_mode is not None:
        query = query.where(AttendanceLog.verify_mode == verify_mode)
    if work_code:
        query = query.where(AttendanceLog.work_code == work_code)
    result = await session.execute(query)
    rows = result.scalars().all()
    return [
        AttendanceOut(
            id=r.id,
            device_id=r.device_id,
            device_user_pin=r.device_user_pin,
            recorded_at=r.recorded_at,
            status=r.status,
            verify_mode=r.verify_mode,
            work_code=r.work_code,
        )
        for r in rows
    ]


device_users_router = APIRouter(prefix="/device-users", tags=["device-users"])


@device_users_router.get("", response_model=list[DeviceUserOut])
async def list_device_users(
    device_id: uuid.UUID | None = None,
    _user: User = Depends(deps.require_permission("device_users.read")),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceUserOut]:
    query = select(DeviceUser).order_by(DeviceUser.pin).limit(200)
    if device_id:
        query = query.where(DeviceUser.device_id == device_id)
    result = await session.execute(query)
    return [
        DeviceUserOut(
            id=r.id,
            device_id=r.device_id,
            pin=r.pin,
            name=r.name,
            privilege=r.privilege,
            card_number=r.card_number,
            enabled=r.enabled,
            sync_state=r.sync_state,
            last_protocol_command_id=r.last_protocol_command_id,
        )
        for r in result.scalars().all()
    ]


def _user_out(row: DeviceUser) -> DeviceUserOut:
    return DeviceUserOut(
        id=row.id,
        device_id=row.device_id,
        pin=row.pin,
        name=row.name,
        privilege=row.privilege,
        card_number=row.card_number,
        enabled=row.enabled,
        sync_state=row.sync_state,
        last_protocol_command_id=row.last_protocol_command_id,
    )


@device_users_router.post("/{device_id}", response_model=DeviceUserOut, status_code=201)
async def create_device_user(
    device_id: uuid.UUID,
    payload: DeviceUserIn,
    user: User = Depends(deps.require_permission("device_users.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> DeviceUserOut:
    """Queue DATA UPDATE USERINFO and record the intent as `pending` (M-03).

    The local row is desired-state, NOT device truth: `sync_state` stays
    `pending` until the device confirms via /iclock/devicecmd.
    """
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    existing = await session.execute(
        select(DeviceUser).where(DeviceUser.device_id == device.id, DeviceUser.pin == payload.pin)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Device user with this PIN already exists")
    from app.adms.commands import CommandBuilder

    ctype, wire = CommandBuilder.update_userinfo(
        pin=payload.pin, name=payload.name, privilege=payload.privilege, card=payload.card
    )
    row = DeviceUser(
        device_id=device.id,
        pin=payload.pin,
        name=payload.name,
        privilege=payload.privilege,
        card_number=payload.card or None,
        sync_state="pending",
        pending_op={
            "op": "create",
            "name": payload.name,
            "privilege": payload.privilege,
            "card": payload.card,
        },
    )
    session.add(row)
    await session.flush()
    await command_svc.queue_command(
        session,
        serial=device.serial_number,
        command_type=CommandType(ctype),
        command=wire,
        created_by=user.id,
        payload={"device_user_id": str(row.id), "op": "create"},
    )
    await audit_svc.record(
        session,
        action="device_user.create",
        user_id=user.id,
        resource_type="device_user",
        resource_id=row.id,
        device_id=device.id,
        request_id=rid,
        metadata={"pin": payload.pin},
    )
    await session.commit()
    return _user_out(row)


@device_users_router.put("/{user_id}", response_model=DeviceUserOut)
async def update_device_user(
    user_id: uuid.UUID,
    payload: DeviceUserUpdate,
    user: User = Depends(deps.require_permission("device_users.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> DeviceUserOut:
    """Queue DATA UPDATE USERINFO for an existing row (M-03, audit device_user.update)."""
    row = await session.get(DeviceUser, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    if row.sync_state == "pending":
        raise HTTPException(status_code=409, detail="A sync operation is already pending")
    device = await session.get(Device, row.device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    changes: dict[str, object] = {}
    name = payload.name if payload.name is not None else row.name
    privilege = payload.privilege if payload.privilege is not None else row.privilege
    card = payload.card if payload.card is not None else (row.card_number or "")
    if payload.enabled is not None:
        row.enabled = payload.enabled
        changes["enabled"] = payload.enabled
    if name != row.name or privilege != row.privilege or card != (row.card_number or ""):
        from app.adms.commands import CommandBuilder

        ctype, wire = CommandBuilder.update_userinfo(
            pin=row.pin, name=name, privilege=privilege, card=card
        )
        row.name = name
        row.privilege = privilege
        row.card_number = card or None
        row.sync_state = "pending"
        row.pending_op = {"op": "update", "name": name, "privilege": privilege, "card": card}
        await session.flush()
        await command_svc.queue_command(
            session,
            serial=device.serial_number,
            command_type=CommandType(ctype),
            command=wire,
            created_by=user.id,
            payload={"device_user_id": str(row.id), "op": "update"},
        )
        changes["sync"] = "pending"
    await audit_svc.record(
        session,
        action="device_user.update",
        user_id=user.id,
        resource_type="device_user",
        resource_id=row.id,
        device_id=row.device_id,
        request_id=rid,
        metadata=changes,
    )
    await session.commit()
    return _user_out(row)


@device_users_router.delete("/{user_id}", response_model=DeviceUserOut, status_code=202)
async def delete_device_user(
    user_id: uuid.UUID,
    user: User = Depends(deps.require_permission("device_users.delete")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> DeviceUserOut:
    """Request removal: the row disappears only after the device confirms
    DATA DELETE USERINFO (M-03). Returns 202 with the pending intent."""
    row = await session.get(DeviceUser, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    if row.sync_state == "pending":
        raise HTTPException(status_code=409, detail="A sync operation is already pending")
    device = await session.get(Device, row.device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    from app.adms.commands import CommandBuilder

    ctype, wire = CommandBuilder.delete_userinfo(pin=row.pin)
    row.sync_state = "pending"
    row.pending_op = {"op": "delete"}
    await session.flush()
    await command_svc.queue_command(
        session,
        serial=device.serial_number,
        command_type=CommandType(ctype),
        command=wire,
        created_by=user.id,
        payload={"device_user_id": str(row.id), "op": "delete"},
    )
    await audit_svc.record(
        session,
        action="device_user.delete",
        user_id=user.id,
        resource_type="device_user",
        resource_id=user_id,
        device_id=row.device_id,
        request_id=rid,
    )
    await session.commit()
    return _user_out(row)


audit_router = APIRouter(prefix="/audit", tags=["audit"])


@audit_router.get("")
async def list_audit(
    limit: int = Query(default=50, le=200),
    _user: User = Depends(deps.require_permission("audit.read")),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    return [
        {
            "action": a.action,
            "user_id": str(a.user_id) if a.user_id else None,
            "resource_type": a.resource_type,
            "request_id": a.request_id,
            "created_at": a.created_at.isoformat(),
            "metadata": a.meta,
        }
        for a in result.scalars().all()
    ]


commands_router = APIRouter(prefix="/commands", tags=["commands"])


@commands_router.get("")
async def list_commands_global(
    status: str | None = None,
    _user: User = Depends(deps.require_permission("commands.read")),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from app.models.device import DeviceCommand

    query = select(DeviceCommand).order_by(DeviceCommand.queued_at.desc()).limit(200)
    if status:
        query = query.where(DeviceCommand.status == status)
    result = await session.execute(query)
    return [
        {
            "id": str(c.id),
            "protocol_command_id": c.protocol_command_id,
            "command_type": c.command_type,
            "status": c.status,
            "return_code": c.return_code,
            "queued_at": c.queued_at.isoformat(),
        }
        for c in result.scalars().all()
    ]
