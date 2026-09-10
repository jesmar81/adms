"""ADMS integration: getrequest / devicecmd / inspect + command flow (async)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.adms.commands import CommandType
from app.core.database import get_db
from app.main import create_app
from app.models.device import DeviceCommand
from app.services import command as command_svc
from app.services import device as device_svc


@pytest_asyncio.fixture
async def async_client(db_session):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _queue(db_session, serial: str, command: str = "CHECK"):  # type: ignore[no-untyped-def]
    device, _ = await device_svc.register_device(db_session, serial)
    await db_session.commit()
    row = await command_svc.queue_command(
        db_session, serial=serial, command_type=CommandType.CHECK, command=command
    )
    await db_session.commit()
    return row


async def test_getrequest_empty_ok(async_client) -> None:  # type: ignore[no-untyped-def]
    response = await async_client.get("/iclock/getrequest?SN=EMPTY001")
    assert response.status_code == 200
    assert response.text == "OK"


async def test_getrequest_delivers_wire_format(async_client, db_session) -> None:  # type: ignore[no-untyped-def]
    await _queue(db_session, "WIRE001")
    first = await async_client.get("/iclock/getrequest?SN=WIRE001")
    assert first.status_code == 200
    assert first.text.startswith("C:1:CHECK")
    second = await async_client.get("/iclock/getrequest?SN=WIRE001")
    assert second.text == "OK"  # drained: no double delivery


async def test_devicecmd_confirms_success(async_client, db_session) -> None:  # type: ignore[no-untyped-def]
    row = await _queue(db_session, "CONF001", "INFO")
    response = await async_client.post(
        "/iclock/devicecmd?SN=CONF001",
        content=f"ID={row.protocol_command_id}&Return=0&CMD=INFO",
    )
    assert response.status_code == 200
    assert response.text == "OK"
    refreshed = await db_session.get(DeviceCommand, row.id, populate_existing=True)
    assert refreshed is not None and refreshed.status == "confirmed"


async def test_devicecmd_failed_return_code(  # type: ignore[no-untyped-def]
    async_client, db_session, settings, monkeypatch
) -> None:
    # L-02: with max_attempts=1 a failed confirmation is terminal.
    monkeypatch.setattr(settings, "zkteco_command_max_attempts", 1)
    row = await _queue(db_session, "FAIL001", "CHECK")
    await async_client.get("/iclock/getrequest?SN=FAIL001")
    await async_client.post(
        "/iclock/devicecmd?SN=FAIL001",
        content=f"ID={row.protocol_command_id}&Return=5&CMD=CHECK",
    )
    refreshed = await db_session.get(DeviceCommand, row.id, populate_existing=True)
    assert refreshed is not None and refreshed.status == "failed"


async def test_devicecmd_unknown_id_still_ok(async_client) -> None:  # type: ignore[no-untyped-def]
    response = await async_client.post(
        "/iclock/devicecmd?SN=UNK001", content="ID=9999&Return=0&CMD=INFO"
    )
    assert response.status_code == 200
    assert response.text == "OK"


async def test_inspect_disabled_404(async_client) -> None:  # type: ignore[no-untyped-def]
    assert (await async_client.get("/iclock/inspect")).status_code == 404


async def test_command_queue_limit(async_client, db_session, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.exceptions import CommandQueueFullError

    monkeypatch.setattr(settings, "zkteco_max_commands_per_device", 1)
    device, _ = await device_svc.register_device(db_session, "QLIM001")
    await db_session.commit()
    await command_svc.queue_command(
        db_session, serial="QLIM001", command_type=CommandType.CHECK, command="CHECK"
    )
    await db_session.commit()
    with pytest.raises(CommandQueueFullError):
        await command_svc.queue_command(
            db_session, serial="QLIM001", command_type=CommandType.CHECK, command="CHECK"
        )
    monkeypatch.setattr(settings, "zkteco_max_commands_per_device", 100)
