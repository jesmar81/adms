"""H-01 regression: Redis-enforced rate limiting + fail-closed auth (fail-open ADMS)."""

from __future__ import annotations

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.core import security
from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app


@pytest_asyncio.fixture
async def rl_client(db_session):  # type: ignore[no-untyped-def]
    from app.models.user import User

    user = User(
        username="rluser",
        email="rl@example.com",
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
        yield client
    app.dependency_overrides.clear()


async def test_login_within_limit_ok(rl_client) -> None:  # type: ignore[no-untyped-def]
    response = await rl_client.post(
        "/api/v1/auth/login", json={"username": "rluser", "password": "s3cret!"}
    )
    assert response.status_code == 200


async def test_login_exceeding_limit_429(rl_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "ratelimit_login_max_attempts", 2)
    monkeypatch.setattr(settings, "ratelimit_lockout_threshold", 1000)
    for _ in range(2):
        response = await rl_client.post(
            "/api/v1/auth/login", json={"username": "rluser", "password": "wrong"}
        )
        assert response.status_code == 401
    blocked = await rl_client.post(
        "/api/v1/auth/login", json={"username": "rluser", "password": "wrong"}
    )
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in blocked.headers


async def test_account_lockout_after_failures(rl_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "ratelimit_login_max_attempts", 1000)
    monkeypatch.setattr(settings, "ratelimit_lockout_threshold", 3)
    for _ in range(3):
        response = await rl_client.post(
            "/api/v1/auth/login", json={"username": "rluser", "password": "wrong"}
        )
        assert response.status_code == 401
    locked = await rl_client.post(
        "/api/v1/auth/login", json={"username": "rluser", "password": "s3cret!"}
    )
    assert locked.status_code == 429


async def test_refresh_exceeding_limit_429(rl_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "ratelimit_refresh_max_attempts", 1000)
    tokens = (
        await rl_client.post(
            "/api/v1/auth/login", json={"username": "rluser", "password": "s3cret!"}
        )
    ).json()
    monkeypatch.setattr(settings, "ratelimit_refresh_max_attempts", 1)
    first = await rl_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert first.status_code == 200
    second = await rl_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first.json()["refresh_token"]}
    )
    assert second.status_code == 429


async def test_adms_normal_polling_ok(rl_client) -> None:  # type: ignore[no-untyped-def]
    for _ in range(5):
        response = await rl_client.get("/iclock/getrequest?SN=RLNORM")
        assert response.status_code == 200


async def test_adms_flood_per_device_429(rl_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "ratelimit_adms_device_max", 3)
    for _ in range(3):
        assert (await rl_client.get("/iclock/getrequest?SN=RLFLOOD")).status_code == 200
    flooded = await rl_client.get("/iclock/getrequest?SN=RLFLOOD")
    assert flooded.status_code == 429
    assert flooded.headers["content-type"].startswith("text/plain")
    # Isolation: another serial is unaffected.
    assert (await rl_client.get("/iclock/getrequest?SN=RLOTHER")).status_code == 200


async def test_limits_shared_across_clients(real_redis) -> None:  # type: ignore[no-untyped-def]
    """Independent real Redis clients share the same distributed budget."""
    from app.core.ratelimit import hit

    second_worker = Redis.from_url(os.environ["ZKTECO_TEST_REDIS_URL"], decode_responses=True)
    try:
        allowed_a, _ = await hit(real_redis, "rl:shared:x", 2, 60)
        allowed_b, _ = await hit(second_worker, "rl:shared:x", 2, 60)
        allowed_c, _ = await hit(real_redis, "rl:shared:x", 2, 60)
        assert (allowed_a, allowed_b, allowed_c) == (True, True, False)
    finally:
        await second_worker.aclose()


async def test_revocation_shared_across_workers(real_redis) -> None:  # type: ignore[no-untyped-def]
    """Revocation written by one Redis client is visible through another."""
    from app.core import revocation

    second_worker = Redis.from_url(os.environ["ZKTECO_TEST_REDIS_URL"], decode_responses=True)
    try:
        await revocation.revoke("jti-worker-a", 60)
        assert await second_worker.get("revoked:jti-worker-a") == "1"
        assert await revocation.is_revoked("jti-worker-a") is True
        assert await revocation.is_revoked("jti-unknown") is False
    finally:
        await second_worker.aclose()


async def test_redis_down_login_fail_closed(rl_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/15")
    get_redis.cache_clear()
    response = await rl_client.post(
        "/api/v1/auth/login", json={"username": "rluser", "password": "s3cret!"}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


async def test_redis_down_authed_503(rl_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    tokens = (
        await rl_client.post(
            "/api/v1/auth/login", json={"username": "rluser", "password": "s3cret!"}
        )
    ).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await rl_client.get("/api/v1/devices", headers=headers)).status_code == 200

    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/15")
    get_redis.cache_clear()
    response = await rl_client.get("/api/v1/devices", headers=headers)
    assert response.status_code == 503


async def test_redis_down_adms_fail_open(rl_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/15")
    get_redis.cache_clear()
    # Attendance ingestion stays available even without Redis (documented trade-off).
    response = await rl_client.post(
        "/iclock/cdata?SN=RLDOWN&table=ATTLOG", content="1\t2024-03-15 08:30:00\t0\t1\t"
    )
    assert response.status_code == 200
    assert response.text.startswith("OK")
