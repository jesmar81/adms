"""Command queue manager — mirrors Laravel `CommandManager` + concurrency (§43, M-08).

- `protocol_command_id`: allocated with an atomic per-device counter
  (`UPDATE devices SET command_seq = command_seq + 1 RETURNING`), so
  concurrent queue calls can never collide — on PostgreSQL the row lock
  serializes writers; SQLite serializes writers by design.
- `drain_for_device`: SELECT ... FOR UPDATE SKIP LOCKED (PG) so concurrent
  polls never deliver the same command twice.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adms.commands import CommandType
from app.adms.parser import CommandResult, parse_info_command_response
from app.core.config import get_settings
from app.core.constants import (
    COMMAND_STATUS_CANCELLED,
    COMMAND_STATUS_CONFIRMED,
    COMMAND_STATUS_EXPIRED,
    COMMAND_STATUS_FAILED,
    COMMAND_STATUS_PENDING,
    COMMAND_STATUS_SENT,
)
from app.core.exceptions import CommandQueueFullError, DeviceDisabledError, DeviceNotFoundError
from app.models.device import Device, DeviceCommand
from app.services import device as device_svc
from app.services import events as event_svc


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _dialect_name(session: AsyncSession) -> str:
    try:
        bind = session.get_bind()
        if bind is None:
            return "postgresql"
        return str(bind.dialect.name)
    except Exception:
        return "postgresql"


async def _get_device(session: AsyncSession, serial: str) -> Device:
    result = await session.execute(select(Device).where(Device.serial_number == serial))
    device = result.scalar_one_or_none()
    if device is None:
        raise DeviceNotFoundError(f"Device not found: {serial!r}")
    return device


async def pending_count(session: AsyncSession, device: Device) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(DeviceCommand)
        .where(
            DeviceCommand.device_id == device.id,
            DeviceCommand.status.in_([COMMAND_STATUS_PENDING, COMMAND_STATUS_SENT]),
        )
    )
    return int(result.scalar_one())


async def queue_command(
    session: AsyncSession,
    *,
    serial: str,
    command_type: CommandType,
    command: str,
    created_by: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> DeviceCommand:
    device = await _get_device(session, serial)
    if device.status == "disabled":
        raise DeviceDisabledError(f"Device is disabled: {serial!r}")
    limit = get_settings().zkteco_max_commands_per_device
    if limit > 0 and await pending_count(session, device) >= limit:
        raise CommandQueueFullError(f"Command queue full for device {serial} (limit: {limit})")
    # Atomic per-device counter (M-08): a single UPDATE takes the row lock,
    # so concurrent transactions serialize and IDs can never collide.
    new_seq = await session.scalar(
        update(Device)
        .where(Device.id == device.id)
        .values(command_seq=Device.command_seq + 1)
        .returning(Device.command_seq)
    )
    if new_seq is None:
        raise DeviceNotFoundError(f"Device not found: {serial!r}")
    device.command_seq = int(new_seq)
    now = _utcnow()
    row = DeviceCommand(
        device_id=device.id,
        protocol_command_id=int(new_seq),
        command_type=command_type.value,
        command=command,
        payload=payload,
        status=COMMAND_STATUS_PENDING,
        queued_at=now,
        expires_at=now + timedelta(seconds=get_settings().zkteco_command_ttl_s),
        created_by=created_by,
    )
    session.add(row)
    await session.flush()
    await event_svc.emit(
        session,
        device_id=device.id,
        event_type="command_queued",
        payload={"protocol_command_id": row.protocol_command_id, "type": command_type.value},
    )
    return row


async def drain_for_device(session: AsyncSession, device: Device) -> list[DeviceCommand]:
    """Return pending commands oldest-first, marking them sent (row-locked).

    Lifecycle policy (L-02), applied before delivery:
    - past `expires_at` → `expired` (never delivered);
    - `attempt_count >= max_attempts` → `failed` (poison commands don't loop).
    """
    settings = get_settings()
    now = _utcnow()
    await expire_commands(session, device=device, now=now)
    query = (
        select(DeviceCommand)
        .where(DeviceCommand.device_id == device.id, DeviceCommand.status == COMMAND_STATUS_PENDING)
        .order_by(DeviceCommand.protocol_command_id)
    )
    if _dialect_name(session) == "postgresql":
        query = query.with_for_update(skip_locked=True)
    result = await session.execute(query)
    rows = list(result.scalars().all())
    deliverable: list[DeviceCommand] = []
    for row in rows:
        if row.attempt_count >= settings.zkteco_command_max_attempts:
            row.status = COMMAND_STATUS_FAILED
            row.error_message = f"max attempts reached ({settings.zkteco_command_max_attempts})"
            continue
        deliverable.append(row)
    for row in deliverable:
        row.status = COMMAND_STATUS_SENT
        row.sent_at = now
        row.attempt_count += 1
        row.last_attempt_at = now
    await session.flush()
    if deliverable:
        await event_svc.emit(
            session,
            device_id=device.id,
            event_type="command_sent",
            payload={"count": len(deliverable)},
        )
        device.last_command_poll_at = now
    return deliverable


async def confirm_result(
    session: AsyncSession, *, device: Device, result: CommandResult, response: str = ""
) -> DeviceCommand | None:
    query = select(DeviceCommand).where(
        DeviceCommand.device_id == device.id,
        DeviceCommand.protocol_command_id == result.protocol_command_id,
    )
    found = await session.execute(query)
    row = found.scalar_one_or_none()
    if row is None:
        await event_svc.emit(
            session,
            device_id=device.id,
            event_type="adms_error",
            payload={"unknown_command_id": result.protocol_command_id},
            severity="warning",
        )
        return None
    now = _utcnow()
    # Idempotent confirmation (M-04): device retries of an already-recorded
    # result are acknowledged without duplicating state or events.
    if row.status in (COMMAND_STATUS_CONFIRMED, COMMAND_STATUS_FAILED):
        if row.return_code == result.return_code:
            return row
    from app.services import device_user as device_user_svc

    settings = get_settings()
    if result.is_success:
        row.return_code = result.return_code
        row.confirmed_at = now
        row.response = response
        row.status = COMMAND_STATUS_CONFIRMED
        device.last_command_result_at = now
        if row.command_type == CommandType.INFO.value:
            info = parse_info_command_response(response)
            if info:
                device_svc.merge_options(device, info)
                device.last_device_info = info
                await event_svc.emit(
                    session,
                    device_id=device.id,
                    event_type="device_info_received",
                    payload={"source": "devicecmd", "option_count": len(info)},
                )
        await session.flush()
        await event_svc.emit(
            session,
            device_id=device.id,
            event_type="command_confirmed",
            payload={
                "protocol_command_id": row.protocol_command_id,
                "return_code": result.return_code,
            },
            severity="info",
        )
        # Reconcile linked device-user intents (M-03).
        await device_user_svc.reconcile_command(session, command=row, success=True)
        return row
    # Failure: retry while attempts remain (L-02), else terminal failure.
    row.return_code = result.return_code
    row.response = response
    if row.attempt_count >= settings.zkteco_command_max_attempts:
        row.status = COMMAND_STATUS_FAILED
        row.confirmed_at = now
        device.last_command_result_at = now
        await session.flush()
        await event_svc.emit(
            session,
            device_id=device.id,
            event_type="command_failed",
            payload={
                "protocol_command_id": row.protocol_command_id,
                "return_code": result.return_code,
            },
            severity="warning",
        )
        await device_user_svc.reconcile_command(session, command=row, success=False)
        return row
    row.status = COMMAND_STATUS_PENDING
    device.last_command_result_at = now
    await session.flush()
    await event_svc.emit(
        session,
        device_id=device.id,
        event_type="command_retry",
        payload={
            "protocol_command_id": row.protocol_command_id,
            "return_code": result.return_code,
            "attempt": row.attempt_count,
        },
        severity="warning",
    )
    return row


async def cancel_command(session: AsyncSession, command_id: uuid.UUID) -> DeviceCommand | None:
    result = await session.execute(select(DeviceCommand).where(DeviceCommand.id == command_id))
    row = result.scalar_one_or_none()
    if row is None or row.status not in (COMMAND_STATUS_PENDING, COMMAND_STATUS_SENT):
        return None
    row.status = COMMAND_STATUS_CANCELLED
    await session.flush()
    return row


async def expire_commands(
    session: AsyncSession, *, device: Device, now: datetime | None = None
) -> int:
    """Mark pending/sent commands past expires_at as expired (L-02).

    Linked device-user intents reconcile as failed — an expired command will
    never be confirmed by the device.
    """
    from app.services import device_user as device_user_svc

    now = now or _utcnow()
    result = await session.execute(
        select(DeviceCommand).where(
            DeviceCommand.device_id == device.id,
            DeviceCommand.status.in_([COMMAND_STATUS_PENDING, COMMAND_STATUS_SENT]),
            DeviceCommand.expires_at.is_not(None),
            DeviceCommand.expires_at < now,
        )
    )
    rows = list(result.scalars().all())
    for row in rows:
        row.status = COMMAND_STATUS_EXPIRED
        await session.flush()
        await device_user_svc.reconcile_command(session, command=row, success=False)
    await session.flush()
    return len(rows)
