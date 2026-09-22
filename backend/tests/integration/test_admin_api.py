"""Admin API integration: devices, attendance, device-users, commands, users, audit."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core import security
from app.core.database import get_db
from app.main import create_app


@pytest_asyncio.fixture
async def admin_client(db_session):  # type: ignore[no-untyped-def]
    from app.models.user import User

    user = User(
        username="root",
        email="root@example.com",
        password_hash=security.hash_password("s3cret!"),
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "root", "password": "s3cret!"}
        )
        assert login.status_code == 200, login.text
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client
    app.dependency_overrides.clear()


async def _register_device(admin_client, serial: str = "ADM001") -> str:  # type: ignore[no-untyped-def]
    response = await admin_client.post("/iclock/registry?SN=" + serial, content="~DeviceName=D1")
    assert response.status_code == 200
    devices = (await admin_client.get("/api/v1/devices")).json()
    match = [d for d in devices if d["serial_number"] == serial]
    assert match, devices
    return str(match[0]["id"])


async def test_devices_list_get_disable_events(admin_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _register_device(admin_client)
    assert (await admin_client.get("/api/v1/devices")).status_code == 200
    detail = await admin_client.get(f"/api/v1/devices/{device_id}")
    assert detail.status_code == 200
    assert detail.json()["derived_status"] in ("online", "offline", "unknown", "stale")
    events = await admin_client.get(f"/api/v1/devices/{device_id}/events")
    assert events.status_code == 200 and len(events.json()) >= 1
    disabled = await admin_client.patch(f"/api/v1/devices/{device_id}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    rejected = await admin_client.post(
        "/iclock/cdata?SN=ADM001&table=ATTLOG",
        content="1001\t2024-03-15 08:30:00\t0\t15\t",
    )
    assert rejected.status_code == 403
    assert (
        await admin_client.get("/api/v1/devices/00000000-0000-0000-0000-000000000000")
    ).status_code == 404


async def test_unknown_device_requires_explicit_provisioning(
    admin_client, settings, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "zkteco_auto_register_unknown", False)
    unknown = await admin_client.post("/iclock/registry?SN=PROVISION1", content="DeviceType=acc")
    assert unknown.status_code == 403
    created = await admin_client.post(
        "/api/v1/devices",
        json={
            "serial_number": "PROVISION1",
            "name": "Laboratorio seguro",
            "model": "SpeedFace-V5L",
            "timezone": "America/Mexico_City",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["last_activity_at"] is None
    connected = await admin_client.post("/iclock/registry?SN=PROVISION1", content="DeviceType=acc")
    assert connected.status_code == 200


async def test_queue_and_list_commands(admin_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _register_device(admin_client, "ADMCMD")
    created = await admin_client.post(
        f"/api/v1/devices/{device_id}/commands",
        json={"command_type": "CHECK", "params": {}},
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "pending"
    listed = await admin_client.get(f"/api/v1/devices/{device_id}/commands")
    assert len(listed.json()) == 1
    bad = await admin_client.post(
        f"/api/v1/devices/{device_id}/commands",
        json={"command_type": "SHELL", "params": {}},
    )
    assert bad.status_code == 422
    option = await admin_client.post(
        f"/api/v1/devices/{device_id}/commands",
        json={"command_type": "GET_OPTION", "params": {"key": "DeviceName"}},
    )
    assert option.status_code == 201
    assert (await admin_client.get("/api/v1/commands")).status_code == 200
    assert (await admin_client.get("/api/v1/commands?status=pending")).status_code == 200
    summary = await admin_client.get("/api/v1/devices/stats/summary")
    assert summary.json()["pending_commands"] >= 2


async def test_attendance_list_filters(admin_client) -> None:  # type: ignore[no-untyped-def]
    await admin_client.post(
        "/iclock/cdata?SN=ADMATT&table=ATTLOG",
        content="1001\t2024-03-15 08:30:00\t0\t15\t",
    )
    base = "/api/v1/attendance"
    assert len((await admin_client.get(base)).json()) >= 1
    assert len((await admin_client.get(base + "?pin=1001")).json()) >= 1
    assert len((await admin_client.get(base + "?status=0&verify_mode=15")).json()) >= 1
    assert (
        len(
            (
                await admin_client.get(
                    base + "?date_from=2024-01-01T00:00:00Z&date_to=2025-01-01T00:00:00Z"
                )
            ).json()
        )
        >= 1
    )
    assert (await admin_client.get(base + "?work_code=NOPE")).json() == []


async def test_device_users_create_delete(admin_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _register_device(admin_client, "ADMU")
    created = await admin_client.post(
        f"/api/v1/device-users/{device_id}",
        json={"pin": "2001", "name": " pertinent", "privilege": 0, "card": ""},
    )
    assert created.status_code == 201, created.text
    assert created.json()["sync_state"] == "pending"
    user_id = created.json()["id"]
    # Duplicate PIN while pending → 409 (L-01, proven 500 before).
    dup = await admin_client.post(
        f"/api/v1/device-users/{device_id}",
        json={"pin": "2001", "name": "x", "privilege": 0, "card": ""},
    )
    assert dup.status_code == 409
    listed = await admin_client.get(f"/api/v1/device-users?device_id={device_id}")
    assert len(listed.json()) == 1
    # Delete while a sync is pending → 409; delete requests confirmation (202).
    assert (await admin_client.delete(f"/api/v1/device-users/{user_id}")).status_code == 409


async def test_users_and_audit_lists(admin_client) -> None:  # type: ignore[no-untyped-def]
    assert len((await admin_client.get("/api/v1/users")).json()) >= 1
    audit = await admin_client.get("/api/v1/audit")
    assert audit.status_code == 200 and len(audit.json()) >= 1


async def test_logout(admin_client) -> None:  # type: ignore[no-untyped-def]
    login = await admin_client.post(
        "/api/v1/auth/login", json={"username": "root", "password": "s3cret!"}
    )
    tokens = login.json()
    access_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await admin_client.get("/api/v1/devices", headers=access_headers)).status_code == 200
    assert (
        await admin_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers=access_headers,
        )
    ).status_code == 204
    # Refresh after logout is revoked.
    assert (
        await admin_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
    ).status_code == 401
    # M-01: the access token is revoked too — session fully terminated.
    assert (await admin_client.get("/api/v1/devices", headers=access_headers)).status_code == 401
