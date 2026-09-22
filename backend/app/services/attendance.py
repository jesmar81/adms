"""ATTLOG ingestion: bulk user-map + bulk dedup + bulk insert (M-05, §18, §68).

Cost per batch: 2 SELECTs + 1 INSERT regardless of batch size (plus the
payload row), instead of ~3 round-trips per line. Idempotency is exact:
a pre-flight SELECT finds existing keys and `ON CONFLICT DO NOTHING`
covers the residual race window. `work_code` is normalized to `""`
(Laravel's default) so the DB unique backstop works — NULLs are never
equal under UNIQUE semantics.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adms.parser import AttendanceRecord
from app.core.logging import get_logger
from app.models.device import AttendanceAttribution, AttendanceLog, Device, DeviceUser
from app.models.hr import Employment, Site
from app.services import events as event_svc

log = get_logger("attendance")

_SMALLINT_MIN = -(2**15)
_SMALLINT_MAX = 2**15 - 1
# PostgreSQL caps statements at 65535 bind parameters and SQLite builds at
# 32766 variables; chunk well below both (1000 rows × 17 cols = 17000).
_CHUNK_SIZE = 1000


def _chunks[T](items: list[T], size: int = _CHUNK_SIZE) -> Iterator[list[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _dialect_name(session: AsyncSession) -> str:
    try:
        bind = session.get_bind()
        if bind is None:
            return "postgresql"
        return str(bind.dialect.name)
    except Exception:
        return "postgresql"


def _coerce_ts(session: AsyncSession, value: datetime) -> datetime:
    """SQLite drops tzinfo on storage; compare/store naive UTC there (PG keeps tz)."""
    if _dialect_name(session) == "sqlite":
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _in_smallint(value: int) -> bool:
    return _SMALLINT_MIN <= value <= _SMALLINT_MAX


def _attendance_day(recorded_at: datetime, timezone: str) -> date:
    tz: tzinfo
    try:
        tz = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        tz = UTC
    aware = recorded_at.replace(tzinfo=UTC) if recorded_at.tzinfo is None else recorded_at
    return aware.astimezone(tz).date()


async def _attribute_inserted(
    session: AsyncSession, *, device: Device, attendance_ids: list[uuid.UUID]
) -> None:
    if not attendance_ids:
        return
    rows = list(
        (
            await session.execute(
                select(AttendanceLog, DeviceUser.person_id)
                .outerjoin(DeviceUser, AttendanceLog.device_user_id == DeviceUser.id)
                .where(AttendanceLog.id.in_(attendance_ids))
            )
        ).tuples()
    )
    site = await session.get(Site, device.site_id) if device.site_id else None
    person_ids = {person_id for _, person_id in rows if person_id is not None}
    employment_query = select(Employment).where(Employment.person_id.in_(person_ids))
    if site is not None:
        employment_query = employment_query.where(Employment.company_id == site.company_id)
    employments = list((await session.execute(employment_query)).scalars()) if person_ids else []
    by_person: dict[uuid.UUID, list[Employment]] = {}
    for employment in employments:
        by_person.setdefault(employment.person_id, []).append(employment)
    now = datetime.now(UTC)
    attributions: list[AttendanceAttribution] = []
    for mark, person_id in rows:
        attendance_day = _attendance_day(mark.recorded_at, mark.device_timezone or device.timezone)
        candidates = [
            employment
            for employment in (by_person.get(person_id, []) if person_id is not None else [])
            if employment.started_on <= attendance_day
            and (employment.ended_on is None or employment.ended_on >= attendance_day)
        ]
        if person_id is None:
            status, reason = "unassigned", "Device PIN is not linked to a person"
        elif len(candidates) == 0:
            status, reason = (
                "unassigned",
                "No employment matches device company and date"
                if site is not None
                else "No employment matches person and date",
            )
        elif len(candidates) > 1:
            status, reason = (
                "ambiguous",
                "Multiple employments match device company and date"
                if site is not None
                else "Device has no site and multiple employments match person and date",
            )
        else:
            status, reason = "assigned", None
        attributions.append(
            AttendanceAttribution(
                attendance_log_id=mark.id,
                employment_id=candidates[0].id if len(candidates) == 1 else None,
                status=status,
                method="device_site" if site is not None else "unique_employment",
                reason=reason,
                created_at=now,
                updated_at=now,
            )
        )
    session.add_all(attributions)
    await session.flush()


async def ingest_records(
    session: AsyncSession,
    *,
    device: Device,
    records: list[AttendanceRecord],
    raw_lines: dict[str, str] | None = None,
    raw_payload_id: uuid.UUID | None = None,
) -> int:
    """Insert valid records, skipping duplicates and out-of-range rows."""
    if not records:
        return 0
    now = datetime.now(UTC)
    dialect = _dialect_name(session)

    # 1) One user-map lookup for the whole batch.
    pins = {record.user_id for record in records}
    user_map: dict[str, uuid.UUID] = {}
    if pins:
        found = await session.execute(
            select(DeviceUser.pin, DeviceUser.id).where(
                DeviceUser.device_id == device.id, DeviceUser.pin.in_(sorted(pins))
            )
        )
        user_map = {pin: uid for pin, uid in found.all()}

    # 2) Normalize + filter (SmallInteger range protects the bulk statement).
    normalized: list[tuple[AttendanceRecord, datetime, str]] = []
    skipped_range = 0
    for record in records:
        if not _in_smallint(record.status) or not _in_smallint(record.verify_mode):
            skipped_range += 1
            continue
        normalized.append((record, _coerce_ts(session, record.timestamp), record.work_code or ""))
    if skipped_range:
        log.warning("attendance_rows_out_of_range", count=skipped_range)
    if not normalized:
        return 0

    # 3) Bulk dedup SELECT, chunked (PG bind-parameter ceiling).
    key_tuples = [
        (record.user_id, recorded_at, record.status, record.verify_mode, work_code)
        for record, recorded_at, work_code in normalized
    ]
    seen: set[tuple[object, ...]] = set()
    for key_chunk in _chunks(key_tuples):
        existing = await session.execute(
            select(
                AttendanceLog.device_user_pin,
                AttendanceLog.recorded_at,
                AttendanceLog.status,
                AttendanceLog.verify_mode,
                AttendanceLog.work_code,
            ).where(
                AttendanceLog.device_id == device.id,
                tuple_(
                    AttendanceLog.device_user_pin,
                    AttendanceLog.recorded_at,
                    AttendanceLog.status,
                    AttendanceLog.verify_mode,
                    AttendanceLog.work_code,
                ).in_(key_chunk),
            )
        )
        seen.update({(pin, ts, st, vm, wc or "") for pin, ts, st, vm, wc in existing.all()})

    # 4) One bulk INSERT with ON CONFLICT DO NOTHING (race backstop) + RETURNING.
    values = [
        {
            "id": uuid.uuid4(),
            "device_id": device.id,
            "device_user_id": user_map.get(record.user_id),
            "device_user_pin": record.user_id,
            "recorded_at": recorded_at,
            "device_timezone": device.timezone,
            "status": record.status,
            "verify_mode": record.verify_mode,
            "work_code": work_code,
            "raw_line": record.raw_line
            or (raw_lines or {}).get(record.user_id + record.timestamp.isoformat()),
            "raw_payload_id": raw_payload_id,
            "source": "adms",
            "received_at": now,
            "created_at": now,
        }
        for record, recorded_at, work_code in normalized
        if (record.user_id, recorded_at, record.status, record.verify_mode, work_code) not in seen
    ]
    if not values:
        return 0
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert
    inserted_ids: list[uuid.UUID] = []
    for value_chunk in _chunks(values):
        stmt = (
            insert_fn(AttendanceLog)
            .values(value_chunk)
            .on_conflict_do_nothing(
                index_elements=[
                    "device_id",
                    "device_user_pin",
                    "recorded_at",
                    "status",
                    "verify_mode",
                    "work_code",
                ]
            )
            .returning(AttendanceLog.id)
        )
        result = await session.execute(stmt)
        inserted_ids.extend(result.scalars().all())
    inserted = len(inserted_ids)
    if inserted:
        await _attribute_inserted(session, device=device, attendance_ids=inserted_ids)
        await event_svc.emit(
            session,
            device_id=device.id,
            event_type="attendance_received",
            payload={"count": inserted},
        )
    return inserted
