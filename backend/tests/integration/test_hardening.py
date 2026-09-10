"""L-03/L-04 regression: OpenAPI surface, envelope request_id, ready, CORS,
headers, docs toggle, Password= redaction, trusted proxies."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core import security
from app.core.database import get_db
from app.main import create_app
from app.models.device import AdmsPayload


@pytest_asyncio.fixture
async def hard_client(db_session):  # type: ignore[no-untyped-def]
    from app.models.user import User

    user = User(
        username="hard",
        email="hard@example.com",
        password_hash=security.hash_password("s3cret-pw!"),
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


async def test_openapi_excludes_adms(hard_client) -> None:  # type: ignore[no-untyped-def]
    spec = (await hard_client.get("/openapi.json")).json()
    assert "/api/v1/devices" in spec["paths"]
    assert not [p for p in spec["paths"] if p.startswith("/iclock")]


async def test_error_envelope_has_request_id(hard_client) -> None:  # type: ignore[no-untyped-def]
    response = await hard_client.get(
        "/api/v1/devices/00000000-0000-0000-0000-000000000000",
        headers={"X-Request-ID": "req-123"},
    )
    assert response.status_code == 401  # no auth; envelope still applies below
    unauth = await hard_client.get("/no-such-route", headers={"X-Request-ID": "req-123"})
    assert unauth.status_code == 404
    assert unauth.json()["error"]["request_id"] == "req-123"


async def test_ready_sanitized(hard_client) -> None:  # type: ignore[no-untyped-def]
    response = await hard_client.get("/ready")
    assert response.status_code in (200, 503)
    body = response.json()
    assert set(body["checks"]) == {"postgres", "redis"}
    assert all(isinstance(v, bool) for v in body["checks"].values())
    assert "Error" not in response.text and "error:" not in response.text


async def test_security_headers_present(hard_client) -> None:  # type: ignore[no-untyped-def]
    response = await hard_client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "x-request-id" in response.headers


async def test_cors_explicit_origins(db_session, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "frontend_origins_raw", "https://admin.example.com")

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        preflight = await client.options(
            "/api/v1/devices",
            headers={
                "Origin": "https://admin.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.headers.get("access-control-allow-origin") == "https://admin.example.com"
        evil = await client.options(
            "/api/v1/devices",
            headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in evil.headers
    app.dependency_overrides.clear()
    monkeypatch.setattr(settings, "frontend_origins_raw", "")


async def test_docs_toggle(db_session, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "docs_enabled", False)
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/openapi.json")).status_code == 404
    app.dependency_overrides.clear()
    monkeypatch.setattr(settings, "docs_enabled", True)


async def test_userinfo_password_redacted_in_payload(hard_client, db_session) -> None:  # type: ignore[no-untyped-def]
    await hard_client.post(
        "/iclock/cdata?SN=REDACT1&table=USERINFO",
        content="PIN=5\tName=Spy\tPrivilege=0\tCard=\tPassword=s3cr3t-value",
    )
    await db_session.commit()
    result = await db_session.execute(
        select(AdmsPayload)
        .where(AdmsPayload.data_type == "USERINFO")
        .order_by(AdmsPayload.received_at.desc())
    )
    payload = result.scalars().first()
    assert payload is not None
    assert "s3cr3t-value" not in (payload.raw_body or "")
    assert "Password=***" in (payload.raw_body or "")
    assert len(payload.body_hash) == 64


async def test_xff_trusted_proxy_only(hard_client, db_session, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.models.user import AuditLog

    await hard_client.post(
        "/api/v1/auth/login",
        json={"username": "hard", "password": "s3cret-pw!"},
        headers={"X-Forwarded-For": "9.9.9.9"},
    )
    await db_session.commit()
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "login").order_by(AuditLog.created_at.desc())
    )
    entry = result.scalars().first()
    assert entry is not None
    # Untrusted peer: spoofed XFF ignored.
    assert entry.ip_address != "9.9.9.9"
    # Trusted peer: first XFF hop honored.
    monkeypatch.setattr(settings, "trusted_proxies_raw", "127.0.0.1")
    await hard_client.post(
        "/api/v1/auth/login",
        json={"username": "hard", "password": "s3cret-pw!"},
        headers={"X-Forwarded-For": "9.9.9.9"},
    )
    await db_session.commit()
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "login").order_by(AuditLog.created_at.desc())
    )
    assert result.scalars().first().ip_address == "9.9.9.9"
    monkeypatch.setattr(settings, "trusted_proxies_raw", "")
