"""Gap-closing integration: inspect enabled, revoked tokens, garbage auth."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core import security
from app.core.database import get_db
from app.core.revocation import revoke
from app.main import create_app


@pytest_asyncio.fixture
async def gap_client(db_session):  # type: ignore[no-untyped-def]
    from app.models.user import User

    user = User(
        username="gap",
        email="gap@example.com",
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


async def test_inspect_enabled_returns_snapshot(gap_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "zkteco_enable_inspect", True)
    await gap_client.get("/iclock/registry?SN=INSPECT001")
    response = await gap_client.get("/iclock/inspect")
    assert response.status_code == 200
    assert response.json()["count"] >= 1
    monkeypatch.setattr(settings, "zkteco_enable_inspect", False)


async def test_revoked_access_token_401(gap_client) -> None:  # type: ignore[no-untyped-def]
    login = await gap_client.post(
        "/api/v1/auth/login", json={"username": "gap", "password": "s3cret!"}
    )
    access = login.json()["access_token"]
    claims = security.decode_token(access, security.ACCESS_TYPE)
    await revoke(claims["jti"], 60)
    response = await gap_client.get(
        "/api/v1/devices", headers={"Authorization": f"Bearer {access}"}
    )
    assert response.status_code == 401


async def test_garbage_token_401(gap_client) -> None:  # type: ignore[no-untyped-def]
    response = await gap_client.get(
        "/api/v1/devices", headers={"Authorization": "Bearer garbage.token.here"}
    )
    assert response.status_code == 401


async def test_openapi_exposes_admin_not_adms_rest(gap_client) -> None:  # type: ignore[no-untyped-def]
    spec = (await gap_client.get("/openapi.json")).json()
    assert "/api/v1/devices" in spec["paths"]
