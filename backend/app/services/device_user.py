"""Sync `device_users` from USERINFO pushes (upsert by device+pin) + intent lifecycle (M-03)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adms.parser import UserRecord
from app.core.config import get_settings
from app.models.device import Device, DeviceUser
from app.services import events as event_svc

if TYPE_CHECKING:
    from app.models.device import DeviceCommand


async def sync_from_device(
    session: AsyncSession, *, device: Device, users: list[UserRecord]
) -> int:
    persist_password = get_settings().zkteco_persist_device_password
    now = datetime.now(UTC)
    count = 0
    for user in users:
        result = await session.execute(
            select(DeviceUser).where(DeviceUser.device_id == device.id, DeviceUser.pin == user.pin)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = DeviceUser(
                device_id=device.id,
                pin=user.pin,
                name=user.name,
                privilege=user.privilege,
                card_number=user.card or None,
                device_password=user.password if persist_password and user.password else None,
                raw_data={"Name": user.name, "Privilege": user.privilege, "Card": user.card},
                last_synced_at=now,
            )
            session.add(row)
        else:
            row.name = user.name
            row.privilege = user.privilege
            row.card_number = user.card or None
            if persist_password and user.password:
                row.device_password = user.password
            row.raw_data = {"Name": user.name, "Privilege": user.privilege, "Card": user.card}
            row.last_synced_at = now
            # A device push is authoritative: any pending intent for this PIN
            # is now confirmed by the device itself (M-03 reconciliation).
            if row.sync_state != "synced":
                row.sync_state = "synced"
                row.pending_op = None
        count += 1
    await session.flush()
    if count:
        await event_svc.emit(
            session,
            device_id=device.id,
            event_type="user_query_received",
            payload={"count": count},
        )
    return count


async def reconcile_command(
    session: AsyncSession, *, command: DeviceCommand, success: bool
) -> None:
    """Reconcile a queued user intent with its devicecmd result (M-03).

    - success + op in (create, update) → row `synced`, intent cleared.
    - success + op == delete → row removed (device confirmed removal).
    - failure → row `failed`, intent kept for operator retry.
    """
    payload: dict[str, Any] = command.payload or {}
    link = payload.get("device_user_id")
    if not link:
        return
    try:
        user_id = uuid.UUID(str(link))
    except ValueError:
        return
    row = await session.get(DeviceUser, user_id)
    if row is None:
        return
    row.last_protocol_command_id = command.protocol_command_id
    op = str(payload.get("op", ""))
    if success:
        if op == "delete":
            await event_svc.emit(
                session,
                device_id=row.device_id,
                event_type="user_sync_confirmed",
                payload={
                    "pin": row.pin,
                    "op": op,
                    "protocol_command_id": command.protocol_command_id,
                },
            )
            await session.delete(row)
            await session.flush()
            return
        row.sync_state = "synced"
        row.pending_op = None
        await event_svc.emit(
            session,
            device_id=row.device_id,
            event_type="user_sync_confirmed",
            payload={
                "pin": row.pin,
                "op": op,
                "protocol_command_id": command.protocol_command_id,
            },
        )
    else:
        row.sync_state = "failed"
        await event_svc.emit(
            session,
            device_id=row.device_id,
            event_type="user_sync_failed",
            payload={
                "pin": row.pin,
                "op": op,
                "protocol_command_id": command.protocol_command_id,
                "return_code": command.return_code,
            },
            severity="warning",
        )
    await session.flush()
