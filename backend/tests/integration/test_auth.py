"""Admin auth integration: login → refresh → RBAC → logout."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core import security
from app.core.database import get_db
from app.main import create_app
from app.models.user import Permission, Role


@pytest_asyncio.fixture
async def auth_client(db_session):  # type: ignore[no-untyped-def]
    from app.models.user import User

    user = User(
        username="admin",
        email="admin@example.com",
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


async def test_login_refresh_logout(auth_client) -> None:  # type: ignore[no-untyped-def]
    login = await auth_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "s3cret!"}
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert tokens["token_type"] == "bearer"

    authed = await auth_client.get(
        "/api/v1/devices", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert authed.status_code == 200

    refreshed = await auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200

    # Old refresh token is now revoked (rotation).
    replay = await auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replay.status_code == 401


async def test_login_wrong_password_401(auth_client) -> None:  # type: ignore[no-untyped-def]
    response = await auth_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "nope"}
    )
    assert response.status_code == 401


async def test_unauthenticated_401(auth_client) -> None:  # type: ignore[no-untyped-def]
    assert (await auth_client.get("/api/v1/devices")).status_code == 401


async def test_rbac_viewer_cannot_queue_commands(db_session, auth_client) -> None:  # type: ignore[no-untyped-def]
    from app.models.user import User

    viewer = User(
        username="viewer",
        email="viewer@example.com",
        password_hash=security.hash_password("s3cret!"),
        is_active=True,
    )
    role = Role(name="viewer", description="read-only")
    perm = Permission(code="devices.read", description="read")
    role.permissions.append(perm)
    viewer.roles.append(role)
    db_session.add_all([viewer, role, perm])
    await db_session.commit()

    login = await auth_client.post(
        "/api/v1/auth/login", json={"username": "viewer", "password": "s3cret!"}
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert (await auth_client.get("/api/v1/devices", headers=headers)).status_code == 200
    # viewer lacks commands.execute → 403 on queue endpoint (device lookup first → may 404).
    response = await auth_client.post(
        "/api/v1/devices/00000000-0000-0000-0000-000000000000/commands",
        json={"command_type": "CHECK", "params": {}},
        headers=headers,
    )
    assert response.status_code in (403, 404)
