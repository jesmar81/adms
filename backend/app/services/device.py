"""Device lifecycle: register (idempotent), activity, options, derived status.

Mirrors Laravel `DeviceManager`, minus physical eviction (§46): stale devices
are flagged, never deleted.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adms.exceptions import InvalidSerialNumberError
from app.adms.validators import validate_serial_number
from app.core.config import get_settings
from app.core.constants import (
    DEVICE_STATUS_DISABLED,
    DEVICE_STATUS_OFFLINE,
    DEVICE_STATUS_ONLINE,
    DEVICE_STATUS_STALE,
    DEVICE_STATUS_UNKNOWN,
    OPTION_TO_COLUMN,
)
from app.core.exceptions import DeviceLimitReachedError
from app.models.device import Device
from app.services import events as event_svc


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_aware(value: datetime) -> datetime:
    """Interpret naive legacy timestamps as UTC (§47: never naive internally)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


async def get_by_serial(session: AsyncSession, serial: str) -> Device | None:
    result = await session.execute(select(Device).where(Device.serial_number == serial))
    return result.scalar_one_or_none()


async def register_device(session: AsyncSession, serial: str) -> tuple[Device, bool]:
    """Idempotent register. Returns (device, created). Enforces max_devices."""
    if not validate_serial_number(serial):
        raise InvalidSerialNumberError(serial)
    device = await get_by_serial(session, serial)
    if device is not None:
        return device, False
    settings = get_settings()
    if settings.zkteco_max_devices > 0:
        # Serialize concurrent registrations so the cap is exact (M-08).
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('zkteco:device_register'))")
        )
        count = await session.scalar(select(func.count()).select_from(Device))
        if (count or 0) >= settings.zkteco_max_devices:
            raise DeviceLimitReachedError(f"Device limit reached ({settings.zkteco_max_devices})")
    now = _utcnow()
    device = Device(
        serial_number=serial,
        status=DEVICE_STATUS_UNKNOWN,
        options={},
        extra_metadata={},
        timezone=settings.zkteco_default_timezone,
        registered_at=now,
        last_activity_at=now,
    )
    session.add(device)
    await session.flush()
    await event_svc.emit(
        session, device_id=device.id, event_type="device_registered", payload={"serial": serial}
    )
    return device, True


async def touch_activity(
    session: AsyncSession, device: Device, *, field: str = "last_activity_at"
) -> bool:
    """Update activity timestamps. Returns True on offline→online transition."""
    was_online = is_online(device)
    now = _utcnow()
    device.last_activity_at = now
    setattr(device, field, now)
    await session.flush()
    became_online = not was_online and is_online(device)
    if became_online:
        await event_svc.emit(session, device_id=device.id, event_type="device_online", payload={})
    return became_online


def is_online(device: Device, *, now: datetime | None = None) -> bool:
    if device.status == DEVICE_STATUS_DISABLED:
        return False
    if device.last_activity_at is None:
        return False
    now = _ensure_aware(now or _utcnow())
    threshold = get_settings().zkteco_online_threshold
    age = (now - _ensure_aware(device.last_activity_at)).total_seconds()
    return age <= threshold


def derived_status(device: Device, *, now: datetime | None = None) -> str:
    """Derive online/offline/stale (never persisted as source of truth, §45)."""
    if device.status == DEVICE_STATUS_DISABLED:
        return DEVICE_STATUS_DISABLED
    if device.last_activity_at is None:
        return DEVICE_STATUS_UNKNOWN
    now = _ensure_aware(now or _utcnow())
    age = (now - _ensure_aware(device.last_activity_at)).total_seconds()
    if age <= get_settings().zkteco_online_threshold:
        return DEVICE_STATUS_ONLINE
    if age <= get_settings().zkteco_stale_after:
        return DEVICE_STATUS_OFFLINE
    return DEVICE_STATUS_STALE


def merge_options(device: Device, new_options: dict[str, str]) -> None:
    """Merge raw options (never drop unknown keys) + sync normalized columns (§13)."""
    merged = dict(device.options or {})
    merged.update(new_options)
    device.options = merged
    for opt_key, column in OPTION_TO_COLUMN.items():
        if opt_key in new_options:
            setattr(device, column, new_options[opt_key] or None)
