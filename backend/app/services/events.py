"""Persist device events (Laravel Events → rows in `device_events`)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import DeviceEvent


async def emit(
    session: AsyncSession,
    *,
    device_id: uuid.UUID | None,
    event_type: str,
    payload: dict[str, Any] | None = None,
    severity: str = "info",
) -> DeviceEvent:
    event = DeviceEvent(
        id=uuid.uuid4(),
        device_id=device_id,
        event_type=event_type,
        severity=severity,
        payload=payload or {},
        created_at=datetime.now(UTC),
    )
    session.add(event)
    return event
