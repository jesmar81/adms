"""Targeted coverage for remediation branches (no filler asserts)."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core import security
from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app


@pytest_asyncio.fixture
async def cov_client(db_session):  # type: ignore[no-untyped-def]
    from app.models.user import User

    admin = User(
        username="cov",
        email="cov@example.com",
        password_hash=security.hash_password("s3cret-pw!"),
        is_active=True,
        is_superuser=True,
    )
    db_session.add(admin)
    await db_session.commit()

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "cov", "password": "s3cret-pw!"}
        )
        assert login.status_code == 200
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client
    app.dependency_overrides.clear()


async def test_me_and_401_envelope(cov_client) -> None:  # type: ignore[no-untyped-def]
    me = await cov_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["username"] == "cov" and "devices.read" in body["permissions"]
    transport = cov_client._transport
    async with AsyncClient(transport=transport, base_url="http://test") as anon:
        denied = await anon.get("/api/v1/auth/me", headers={"X-Request-ID": "r-1"})
        assert denied.status_code == 401
        assert denied.json()["error"]["request_id"] == "r-1"


async def test_login_non_json_body_422(cov_client) -> None:  # type: ignore[no-untyped-def]
    transport = cov_client._transport
    async with AsyncClient(transport=transport, base_url="http://test") as anon:
        response = await anon.post(
            "/api/v1/auth/login", content="not-json", headers={"Content-Type": "text/plain"}
        )
        assert response.status_code == 422
        # L-03: no filesystem paths or handler names leak in 422 bodies.
        assert "app/api" not in response.text
        assert "in create_user" not in response.text and "in login" not in response.text


async def test_redis_down_refresh_and_logout_503(cov_client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def _boom(cls, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RedisConnectionError("down")

    monkeypatch.setattr("redis.asyncio.Redis.from_url", classmethod(_boom))
    get_redis.cache_clear()
    assert (
        await cov_client.post("/api/v1/auth/refresh", json={"refresh_token": "x"})
    ).status_code in (401, 503)
    logout = await cov_client.post("/api/v1/auth/logout", json={"refresh_token": "x"})
    assert logout.status_code == 503


async def test_operator_subset_role_grant(cov_client, db_session) -> None:  # type: ignore[no-untyped-def]
    from app.models.user import Permission, Role, User

    writers = Role(name="writers", description="w")
    writers.permissions.append(Permission(code="users.write", description="w"))
    mgr = User(
        username="mgr2",
        email="mgr2@example.com",
        password_hash=security.hash_password("s3cret-pw!"),
        is_active=True,
    )
    mgr.roles.append(writers)
    db_session.add_all([mgr, writers])
    await db_session.commit()
    transport = cov_client._transport
    from httpx import AsyncClient as AC

    async with AC(transport=transport, base_url="http://test") as raw:
        login = await raw.post(
            "/api/v1/auth/login", json={"username": "mgr2", "password": "s3cret-pw!"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        ok_role = Role(name="limited", description="l")
        ok_perm = Permission(code="users.read", description="r")
        ok_role.permissions.append(ok_perm)
        db_session.add_all([ok_role, ok_perm])
        await db_session.commit()
        # users.write does not include users.read → granting "limited" is forbidden.
        denied = await raw.post(
            "/api/v1/users",
            json={
                "username": "zed1",
                "email": "z1@example.com",
                "password": "longpassword1",
                "role_names": ["limited"],
            },
            headers=headers,
        )
        assert denied.status_code == 403


async def test_users_edge_cases(cov_client) -> None:  # type: ignore[no-untyped-def]
    base = "/api/v1/users"
    assert (await cov_client.get(f"{base}/00000000-0000-0000-0000-000000000000")).status_code == 404
    assert (
        await cov_client.patch(
            "00000000-0000-0000-0000-000000000000".join([base + "/", ""]), json={"email": "a@b.co"}
        )
    ).status_code == 404
    gone = await cov_client.delete(f"{base}/00000000-0000-0000-0000-000000000000")
    assert gone.status_code == 404
    created = await cov_client.post(
        base, json={"username": "edge", "email": "edge@example.com", "password": "longpassword1"}
    )
    uid = created.json()["id"]
    assert (await cov_client.patch(f"{base}/{uid}", json={"email": "bad"})).status_code == 422
    assert (
        await cov_client.patch(f"{base}/{uid}", json={"role_names": ["ghost"]})
    ).status_code == 422
    disabled = await cov_client.patch(f"{base}/{uid}", json={"is_active": False})
    assert disabled.json()["is_active"] is False
    enabled = await cov_client.patch(f"{base}/{uid}", json={"is_active": True})
    assert enabled.json()["is_active"] is True
    # Second superuser can be removed while another remains.
    other = await cov_client.post(
        base,
        json={
            "username": "edge2",
            "email": "edge2@example.com",
            "password": "longpassword1",
            "is_superuser": True,
        },
    )
    assert (await cov_client.delete(f"{base}/{other.json()['id']}")).status_code == 204


async def test_devices_edge_cases(cov_client) -> None:  # type: ignore[no-untyped-def]
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await cov_client.get(f"/api/v1/devices/{missing}")).status_code == 404
    patched = await cov_client.patch(f"/api/v1/devices/{missing}", json={"name": "x"})
    assert patched.status_code == 404
    assert (await cov_client.patch(f"/api/v1/devices/{missing}/disable")).status_code == 404
    assert (
        await cov_client.post(
            f"/api/v1/devices/{missing}/commands", json={"command_type": "CHECK", "params": {}}
        )
    ).status_code == 404
    await cov_client.post("/iclock/registry?SN=EDGEDEV", content="~DeviceName=E")
    devices = (await cov_client.get("/api/v1/devices?status=unknown")).json()
    assert any(d["serial_number"] == "EDGEDEV" for d in devices)
    dev_id = next(d["id"] for d in devices if d["serial_number"] == "EDGEDEV")
    assert (await cov_client.get(f"/api/v1/devices/{dev_id}/events")).status_code == 200
    noop = await cov_client.patch(f"/api/v1/devices/{dev_id}", json={})
    assert noop.status_code == 200


async def test_device_users_missing_device(cov_client) -> None:  # type: ignore[no-untyped-def]
    missing = "00000000-0000-0000-0000-000000000000"
    assert (
        await cov_client.post(
            f"/api/v1/device-users/{missing}",
            json={"pin": "1", "name": "n", "privilege": 0, "card": ""},
        )
    ).status_code == 404
    put = await cov_client.put(f"/api/v1/device-users/{missing}", json={"name": "n"})
    assert put.status_code == 404


async def test_adms_sn_validation_matrix(cov_client) -> None:  # type: ignore[no-untyped-def]
    for path in ("/iclock/cdata", "/iclock/registry", "/iclock/getrequest"):
        assert (await cov_client.get(path)).status_code == 400
        assert (await cov_client.get(path + "?SN=bad%20sn")).status_code == 400
    assert (await cov_client.post("/iclock/devicecmd")).status_code == 400
    assert (await cov_client.post("/iclock/devicecmd?SN=bad%20sn")).status_code == 400
    assert (await cov_client.post("/iclock/cdata?SN=bad%20sn")).status_code == 400


async def test_registry_oversized_413(cov_client, settings) -> None:  # type: ignore[no-untyped-def]
    big = "X" * (settings.zkteco_max_body_size + 1)
    assert (await cov_client.post("/iclock/registry?SN=BIG1", content=big)).status_code == 413


async def test_registry_failure_returns_500(cov_client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.services import device as device_svc

    def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("merge down")

    monkeypatch.setattr(device_svc, "merge_options", _boom)
    response = await cov_client.post("/iclock/registry?SN=R500", content="~A=B")
    assert response.status_code == 500
    assert response.text == "ERROR"


async def test_devicecmd_failure_stays_ok(cov_client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.services import command as command_svc

    async def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("confirm down")

    monkeypatch.setattr(command_svc, "confirm_result", _boom)
    response = await cov_client.post("/iclock/devicecmd?SN=D500", content="ID=1&Return=0&CMD=X")
    assert response.status_code == 200
    assert response.text == "OK"


async def test_adms_ip_flood_429(cov_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "ratelimit_adms_device_max", 100000)
    monkeypatch.setattr(settings, "ratelimit_adms_ip_max", 4)
    for i in range(4):
        assert (await cov_client.get(f"/iclock/getrequest?SN=IPF{i}")).status_code == 200
    assert (await cov_client.get("/iclock/getrequest?SN=IPF9")).status_code == 429
    monkeypatch.setattr(settings, "ratelimit_adms_device_max", 600)
    monkeypatch.setattr(settings, "ratelimit_adms_ip_max", 3000)


async def test_attlog_out_of_range_skipped(cov_client) -> None:  # type: ignore[no-untyped-def]
    body = "1\t2024-03-15 08:30:00\t999999999999\t1\t\n2\t2024-03-15 08:31:00\t0\t1\t"
    response = await cov_client.post("/iclock/cdata?SN=RANGE1&table=ATTLOG", content=body)
    assert response.text == "OK: 1"


def test_database_helpers() -> None:  # type: ignore[no-untyped-def]
    from app.core.database import get_engine, get_session_factory, reset_engine_for_tests

    reset_engine_for_tests()
    assert get_engine() is get_engine()
    assert get_session_factory() is get_session_factory()
    reset_engine_for_tests()


def test_peer_trust_and_client_ip(settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import asyncio

    from fastapi import Request

    from app.api.v1.deps import _peer_trusted, client_ip

    def _req(peer: str, xff: str | None):  # type: ignore[no-untyped-def]
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": headers,
                "client": (peer, 1234),
            }
        )

    monkeypatch.setattr(settings, "trusted_proxies_raw", "10.0.0.0/8, bad-cidr-[")
    assert _peer_trusted("10.1.2.3") is True
    assert _peer_trusted("9.9.9.9") is False
    assert asyncio.run(client_ip(_req("9.9.9.9", "1.2.3.4"), "1.2.3.4")) == "9.9.9.9"
    assert asyncio.run(client_ip(_req("10.1.2.3", "1.2.3.4"), "1.2.3.4")) == "1.2.3.4"
    assert asyncio.run(client_ip(_req("", None), None)) == ""
    monkeypatch.setattr(settings, "trusted_proxies_raw", "")


def test_cli_in_process(tmp_path, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import asyncio

    from sqlalchemy.ext.asyncio import create_async_engine

    import app.models.device  # noqa: F401
    import app.models.user  # noqa: F401
    from app import cli
    from app.models.base import Base

    db = tmp_path / "cli2.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db}")

    async def _make() -> None:
        eng = create_async_engine(f"sqlite+aiosqlite:///{db}")
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

    asyncio.run(_make())
    monkeypatch.setenv("ZKTECO_ADMIN_USERNAME", "cliadmin")
    monkeypatch.setenv("ZKTECO_ADMIN_EMAIL", "cli@example.com")
    monkeypatch.setenv("ZKTECO_ADMIN_PASSWORD", "cli-password-1")
    assert cli.main(["createsuperuser", "--no-input"]) == 0
    assert cli.main(["createsuperuser", "--no-input"]) == 1
    monkeypatch.delenv("ZKTECO_ADMIN_PASSWORD")
    assert cli.main(["createsuperuser", "--no-input"]) == 2
    monkeypatch.setenv("ZKTECO_ADMIN_PASSWORD", "cli-password-1")
    assert cli.main(["createsuperuser", "--username", "a", "--email", "bad"]) == 2
