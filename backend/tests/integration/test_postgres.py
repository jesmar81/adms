"""M-06: PostgreSQL integration — native types, constraints, indexes, concurrency.

Runs ONLY when ZKTECO_TEST_PG_URL is set (CI postgres job + local PG).
SQLite can never prove UUID/JSONB/INET/TIMESTAMPTZ/SKIP LOCKED behavior.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import pytest
import pytest_asyncio
import sqlalchemy
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adms.commands import CommandType
from app.core.database import get_db
from app.main import create_app
from app.models.device import AttendanceLog, Device

pytestmark = pytest.mark.pg


async def _truncate(pg_engine) -> None:  # type: ignore[no-untyped-def]
    from app.models.base import Base

    async with pg_engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(sqlalchemy.text(f"TRUNCATE {tables} CASCADE"))


@pytest_asyncio.fixture
async def pg_pool_client(pg_engine):  # type: ignore[no-untyped-def]
    """App client with a FRESH PG session per request (safe for concurrency)."""

    await _truncate(pg_engine)
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_pg_native_types(pg_session) -> None:  # type: ignore[no-untyped-def]
    device = Device(
        serial_number="PGTYPES",
        options={"FaceCount": "40", "nested": {"a": [1, 2]}},
        ip_address="192.168.1.50",
        mac_address="AA:BB:CC:DD:EE:FF",
        extra_metadata={},
    )
    pg_session.add(device)
    await pg_session.flush()
    log = AttendanceLog(
        device_id=device.id,
        device_user_pin="7",
        recorded_at=datetime(2024, 3, 15, 14, 30, tzinfo=UTC),
        received_at=datetime.now(UTC),
    )
    pg_session.add(log)
    await pg_session.commit()
    dialect_types = await pg_session.execute(
        sqlalchemy.text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name IN ('devices','attendance_logs') AND column_name IN "
            "('id','options','ip_address','recorded_at')"
        )
    )
    seen = {row[0]: row[1] for row in dialect_types.all()}
    assert seen["id"] == "uuid"
    assert seen["options"] == "jsonb"
    assert seen["ip_address"] == "inet"
    assert seen["recorded_at"] == "timestamp with time zone"
    back = await pg_session.execute(select(AttendanceLog))
    assert back.scalar_one().recorded_at.tzinfo is not None


async def test_pg_constraints(pg_session) -> None:  # type: ignore[no-untyped-def]
    pg_session.add(Device(serial_number="PGC", options={}, extra_metadata={}))
    await pg_session.commit()
    pg_session.add(Device(serial_number="PGC", options={}, extra_metadata={}))
    with pytest.raises(IntegrityError):
        await pg_session.commit()
    await pg_session.rollback()
    names = (
        (
            await pg_session.execute(
                sqlalchemy.text(
                    "SELECT conname FROM pg_constraint WHERE conname LIKE 'uq\\_%' ESCAPE '\\'"
                )
            )
        )
        .scalars()
        .all()
    )
    assert {"uq_devices_serial_number", "uq_attendance_dedup", "uq_cmd_device_proto"} <= set(names)
    with pytest.raises(IntegrityError):
        pg_session.add(Device(serial_number="PGBAD", status="nope", options={}, extra_metadata={}))
        await pg_session.commit()
    await pg_session.rollback()


async def test_pg_indexes_exist(pg_session) -> None:  # type: ignore[no-untyped-def]
    rows = (
        (
            await pg_session.execute(
                sqlalchemy.text("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
            )
        )
        .scalars()
        .all()
    )
    for expected in (
        "ix_devices_status",
        "ix_devices_last_activity",
        "ix_device_users_device",
        "ix_attendance_device",
        "ix_attendance_pin",
        "ix_attendance_recorded",
        "ix_attendance_device_recorded",
        "ix_cmd_device",
        "ix_cmd_status",
        "ix_events_device",
        "ix_events_type",
        "ix_events_created",
        "ix_audit_user",
        "ix_audit_device",
        "ix_audit_created",
        "ix_payloads_device_received",
    ):
        assert expected in rows, expected
    # L-02: redundant indexes are gone.
    assert "ix_attendance_device_recorded_desc" not in rows
    assert "ix_cmd_device_proto" not in rows


async def test_pg_attlog_flow_idempotent(pg_pool_client) -> None:  # type: ignore[no-untyped-def]
    body = "1001\t2024-03-15 08:30:00\t0\t15\t"
    first = await pg_pool_client.post("/iclock/cdata?SN=PGFLOW&table=ATTLOG", content=body)
    second = await pg_pool_client.post("/iclock/cdata?SN=PGFLOW&table=ATTLOG", content=body)
    assert (first.text, second.text) == ("OK: 1", "OK: 0")


async def test_pg_bulk_attlog(pg_pool_client) -> None:  # type: ignore[no-untyped-def]
    """M-05 bulk path on real PG (chunked multi-row INSERT ... RETURNING)."""
    import time
    from datetime import UTC, datetime, timedelta

    base = datetime(2024, 3, 15, 8, 0, 0, tzinfo=UTC)
    fmt = "%Y-%m-%d %H:%M:%S"
    lines = [
        f"{(i % 20) + 1}\t{(base + timedelta(seconds=i)).strftime(fmt)}\t{i % 6}\t15\tWC"
        for i in range(5000)
    ]
    body = "\n".join(lines)
    started = time.monotonic()
    response = await pg_pool_client.post("/iclock/cdata?SN=PGBULK&table=ATTLOG", content=body)
    elapsed = time.monotonic() - started
    assert response.text == "OK: 5000"
    assert elapsed < 60, f"bulk took {elapsed:.1f}s"
    again = await pg_pool_client.post("/iclock/cdata?SN=PGBULK&table=ATTLOG", content=body)
    assert again.text == "OK: 0"


async def test_pg_concurrent_getrequest_no_double_delivery(pg_pool_client, pg_engine) -> None:  # type: ignore[no-untyped-def]
    from app.services import command as command_svc
    from app.services import device as device_svc

    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with factory() as session:
        device, _ = await device_svc.register_device(session, "PGPOLL")
        await session.commit()
        for _ in range(3):
            await command_svc.queue_command(
                session, serial="PGPOLL", command_type=CommandType.CHECK, command="CHECK"
            )
        await session.commit()
    responses = await asyncio.gather(
        *[pg_pool_client.get("/iclock/getrequest?SN=PGPOLL") for _ in range(6)]
    )
    assert all(r.status_code == 200 for r in responses)
    delivered: list[int] = []
    for response in responses:
        for line in response.text.splitlines():
            if line.startswith("C:"):
                delivered.append(int(line.split(":")[1]))
    assert sorted(delivered) == [1, 2, 3], delivered


async def test_pg_concurrent_queue_unique_ids(pg_engine) -> None:  # type: ignore[no-untyped-def]
    from app.services import command as command_svc
    from app.services import device as device_svc

    await _truncate(pg_engine)
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with factory() as session:
        await device_svc.register_device(session, "PGSEQ")
        await session.commit()

    async def _one(_: int) -> int:
        async with factory() as session:
            row = await command_svc.queue_command(
                session, serial="PGSEQ", command_type=CommandType.CHECK, command="CHECK"
            )
            await session.commit()
            return row.protocol_command_id

    ids = await asyncio.gather(*[_one(i) for i in range(20)])
    assert sorted(ids) == list(range(1, 21))


async def test_pg_concurrent_register_limit(pg_engine, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.exceptions import DeviceLimitReachedError
    from app.services import device as device_svc

    await _truncate(pg_engine)
    monkeypatch.setattr(settings, "zkteco_max_devices", 3)
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)

    async def _one(i: int) -> bool:
        async with factory() as session:
            try:
                await device_svc.register_device(session, f"PGLIM{i:02d}")
                await session.commit()
                return True
            except DeviceLimitReachedError:
                await session.rollback()
                return False

    results = await asyncio.gather(*[_one(i) for i in range(8)])
    assert sum(results) == 3
    monkeypatch.setattr(settings, "zkteco_max_devices", 1000)


async def test_pg_seed_on_migrated_schema(pg_engine, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings
    from app.models.user import Permission, Role
    from app.seed import main

    assert os.environ["ZKTECO_TEST_PG_URL"]
    await _truncate(pg_engine)
    monkeypatch.setattr(get_settings(), "database_url", os.environ["ZKTECO_TEST_PG_URL"])
    await main()
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with factory() as session:
        role_count = await session.scalar(select(func.count()).select_from(Role))
        perm_count = await session.scalar(select(func.count()).select_from(Permission))
    assert role_count == 3
    assert perm_count == 14
