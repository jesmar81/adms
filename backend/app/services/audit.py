"""Audit log writer (§23, §63)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import AuditLog


async def record(
    session: AsyncSession,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    device_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        device_id=device_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        meta=metadata or {},
        created_at=datetime.now(UTC),
    )
    session.add(entry)
    await session.flush()
    return entry
