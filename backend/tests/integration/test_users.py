"""H-02 regression: user provisioning (API CRUD + CLI) with RBAC guards + audit."""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core import security
from app.core.database import get_db
from app.main import create_app

_BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent.parent


async def _run_cli(env: dict[str, str]) -> tuple[int | None, str, str]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.cli",
        "createsuperuser",
        "--no-input",
        cwd=str(_BACKEND_DIR),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
    return process.returncode, stdout.decode(), stderr.decode()


@pytest_asyncio.fixture
async def users_client(db_session):  # type: ignore[no-untyped-def]
    from app.models.user import Permission, Role, User

    admin = User(
        username="boss",
        email="boss@example.com",
        password_hash=security.hash_password("s3cret-pw!"),
        is_active=True,
        is_superuser=True,
    )
    viewer_role = Role(name="viewer", description="read only")
    viewer_perm = Permission(code="devices.read", description="read")
    viewer_role.permissions.append(viewer_perm)
    viewer = User(
        username="viewer",
        email="viewer@example.com",
        password_hash=security.hash_password("s3cret-pw!"),
        is_active=True,
    )
    viewer.roles.append(viewer_role)
    db_session.add_all([admin, viewer, viewer_role, viewer_perm])
    await db_session.commit()

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        boss = (
            await client.post(
                "/api/v1/auth/login", json={"username": "boss", "password": "s3cret-pw!"}
            )
        ).json()
        client.headers["Authorization"] = f"Bearer {boss['access_token']}"
        yield client
    app.dependency_overrides.clear()


async def _login_as(client, username: str, password: str):  # type: ignore[no-untyped-def]
    transport = client._transport
    async with AsyncClient(transport=transport, base_url="http://test") as fresh:
        return await fresh.post(
            "/api/v1/auth/login", json={"username": username, "password": password}
        )


async def test_create_user_and_login(users_client, db_session) -> None:  # type: ignore[no-untyped-def]
    created = await users_client.post(
        "/api/v1/users",
        json={
            "username": "op1",
            "email": "op1@example.com",
            "password": "long-password-enterprise-1",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["is_active"] is True
    login = await _login_as(users_client, "op1", "long-password-enterprise-1")
    assert login.status_code == 200
    bad = await _login_as(users_client, "op1", "wrongpassword")
    assert bad.status_code == 401
    # Audit generated.
    audit = await users_client.get("/api/v1/audit?limit=50")
    assert any(a["action"] == "user.create" for a in audit.json())


async def test_create_duplicate_409(users_client) -> None:  # type: ignore[no-untyped-def]
    payload = {
        "username": "dup",
        "email": "dup@example.com",
        "password": "long-password-enterprise-1",
    }
    assert (await users_client.post("/api/v1/users", json=payload)).status_code == 201
    assert (await users_client.post("/api/v1/users", json=payload)).status_code == 409


async def test_create_validation(users_client) -> None:  # type: ignore[no-untyped-def]
    short = await users_client.post(
        "/api/v1/users", json={"username": "s", "email": "bad", "password": "x"}
    )
    assert short.status_code == 422
    bad_email = await users_client.post(
        "/api/v1/users",
        json={
            "username": "validname",
            "email": "not-an-email",
            "password": "long-password-enterprise-1",
        },
    )
    assert bad_email.status_code == 422
    unknown_role = await users_client.post(
        "/api/v1/users",
        json={
            "username": "r1",
            "email": "r1@example.com",
            "password": "long-password-enterprise-1",
            "role_names": ["nope"],
        },
    )
    assert unknown_role.status_code == 422


async def test_viewer_cannot_create_user(users_client) -> None:  # type: ignore[no-untyped-def]
    login = await _login_as(users_client, "viewer", "s3cret-pw!")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    transport = users_client._transport
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as v:
        response = await v.post(
            "/api/v1/users",
            json={
                "username": "x",
                "email": "x@example.com",
                "password": "long-password-enterprise-1",
            },
        )
        assert response.status_code == 403


async def test_non_superuser_cannot_create_superuser(users_client, db_session) -> None:  # type: ignore[no-untyped-def]
    from app.models.user import Permission, Role, User

    role = Role(name="usermgr", description="user manager")
    perm = Permission(code="users.write", description="w")
    role.permissions.append(perm)
    mgr = User(
        username="mgr",
        email="mgr@example.com",
        password_hash=security.hash_password("s3cret-pw!"),
        is_active=True,
    )
    mgr.roles.append(role)
    db_session.add_all([mgr, role, perm])
    await db_session.commit()
    login = await _login_as(users_client, "mgr", "s3cret-pw!")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    transport = users_client._transport
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as m:
        evil = await m.post(
            "/api/v1/users",
            json={
                "username": "evil",
                "email": "evil@example.com",
                "password": "long-password-enterprise-1",
                "is_superuser": True,
            },
        )
        assert evil.status_code == 403
        plain = await m.post(
            "/api/v1/users",
            json={
                "username": "plain",
                "email": "plain@example.com",
                "password": "long-password-enterprise-1",
            },
        )
        assert plain.status_code == 201


async def test_company_scoped_manager_cannot_delegate_parent_group(pg_client, pg_session) -> None:  # type: ignore[no-untyped-def]
    from app.models.hr import Company, CorporateGroup
    from app.models.user import Permission, Role, User

    group = CorporateGroup(id=uuid.uuid4(), name="Grupo limitado", code="LIMITED")
    pg_session.add(group)
    await pg_session.flush()
    company = Company(
        corporate_group_id=group.id,
        legal_name="Empresa limitada",
        timezone="America/Mexico_City",
    )
    role = Role(name="scoped_user_manager", description="Scoped user manager")
    permission = Permission(code="users.write", description="Manage users")
    role.permissions.append(permission)
    manager = User(
        username="company-manager",
        email="company-manager@example.com",
        password_hash=security.hash_password("s3cret-pw!"),
        is_active=True,
    )
    manager.roles.append(role)
    manager.company_scopes.append(company)
    pg_session.add_all([company, role, permission, manager])
    await pg_session.commit()

    login = await pg_client.post(
        "/api/v1/auth/login", json={"username": "company-manager", "password": "s3cret-pw!"}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    pg_client.headers.update(headers)
    escalation = await pg_client.post(
        "/api/v1/users",
        json={
            "username": "bad-delegation",
            "email": "bad-delegation@example.com",
            "password": "long-password-enterprise-1",
            "corporate_group_ids": [str(group.id)],
        },
    )
    assert escalation.status_code == 403
    allowed = await pg_client.post(
        "/api/v1/users",
        json={
            "username": "company-only",
            "email": "company-only@example.com",
            "password": "long-password-enterprise-1",
            "company_ids": [str(company.id)],
        },
    )
    assert allowed.status_code == 201


async def test_self_guards(users_client) -> None:  # type: ignore[no-untyped-def]
    me = await users_client.get("/api/v1/users")
    boss = next(u for u in me.json() if u["username"] == "boss")
    # Last superuser: demote/disable rejected with 409; self-delete forbidden.
    demote = await users_client.patch(f"/api/v1/users/{boss['id']}", json={"is_superuser": False})
    assert demote.status_code == 409
    disable = await users_client.patch(f"/api/v1/users/{boss['id']}", json={"is_active": False})
    assert disable.status_code == 409
    delete = await users_client.delete(f"/api/v1/users/{boss['id']}")
    assert delete.status_code in (403, 409)


async def test_last_superuser_protected(users_client) -> None:  # type: ignore[no-untyped-def]
    second = await users_client.post(
        "/api/v1/users",
        json={
            "username": "boss2",
            "email": "boss2@example.com",
            "password": "long-password-enterprise-1",
            "is_superuser": True,
        },
    )
    assert second.status_code == 201
    second_id = second.json()["id"]
    # Now demoting boss is allowed (boss2 remains).
    me = await users_client.get("/api/v1/users")
    boss = next(u for u in me.json() if u["username"] == "boss")
    demote = await users_client.patch(f"/api/v1/users/{boss['id']}", json={"is_superuser": False})
    assert demote.status_code == 200
    # boss2 (still superuser) cannot demote itself as the last superuser.
    login2 = await _login_as(users_client, "boss2", "long-password-enterprise-1")
    headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}
    transport = users_client._transport
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers2) as b2:
        assert (
            await b2.patch(f"/api/v1/users/{second_id}", json={"is_superuser": False})
        ).status_code == 409


async def test_delete_disables_and_blocks_login(users_client) -> None:  # type: ignore[no-untyped-def]
    created = await users_client.post(
        "/api/v1/users",
        json={
            "username": "gone",
            "email": "gone@example.com",
            "password": "long-password-enterprise-1",
        },
    )
    user_id = created.json()["id"]
    assert (await users_client.delete(f"/api/v1/users/{user_id}")).status_code == 204
    assert (await _login_as(users_client, "gone", "long-password-enterprise-1")).status_code == 401
    fetched = await users_client.get(f"/api/v1/users/{user_id}")
    assert fetched.json()["is_active"] is False
    audit = await users_client.get("/api/v1/audit?limit=50")
    assert any(a["action"] == "user.delete" for a in audit.json())
    missing = await users_client.get("/api/v1/users/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


async def test_role_assignment_and_password_change(users_client, db_session) -> None:  # type: ignore[no-untyped-def]
    created = await users_client.post(
        "/api/v1/users",
        json={
            "username": "staff",
            "email": "staff@example.com",
            "password": "long-password-enterprise-1",
            "role_names": ["viewer"],
        },
    )
    assert created.status_code == 201
    assert created.json()["roles"] == ["viewer"]
    user_id = created.json()["id"]
    updated = await users_client.patch(
        f"/api/v1/users/{user_id}",
        json={"password": "brand-new-enterprise-pass-1", "role_names": []},
    )
    assert updated.status_code == 200
    assert (
        await _login_as(users_client, "staff", "brand-new-enterprise-pass-1")
    ).status_code == 200
    audit = await users_client.get("/api/v1/audit?limit=50")
    actions = {a["action"] for a in audit.json()}
    assert {"user.create", "user.update"} <= actions


async def test_cli_createsuperuser(pg_session) -> None:  # type: ignore[no-untyped-def]
    env = dict(
        os.environ,
        DATABASE_URL=os.environ["ZKTECO_TEST_PG_URL"],
        ZKTECO_ADMIN_USERNAME="root",
        ZKTECO_ADMIN_EMAIL="root@example.com",
        ZKTECO_ADMIN_PASSWORD="enterprise-secret-1",
    )
    # pg_session guarantees the schema was built by Alembic and clears rows.
    first_code, first_stdout, first_stderr = await _run_cli(env)
    assert first_code == 0, first_stderr
    assert "created" in first_stdout
    again_code, _, again_stderr = await _run_cli(env)
    assert again_code == 1
    assert "already exists" in again_stderr
    from sqlalchemy import select

    from app.models.user import User

    user = await pg_session.scalar(select(User).where(User.username == "root"))
    assert user is not None and user.email == "root@example.com" and user.is_superuser


async def test_cli_requires_migrated_schema(unmigrated_pg_url) -> None:  # type: ignore[no-untyped-def]
    env = dict(
        os.environ,
        DATABASE_URL=unmigrated_pg_url,
        ZKTECO_ADMIN_USERNAME="root",
        ZKTECO_ADMIN_EMAIL="root@example.com",
        ZKTECO_ADMIN_PASSWORD="enterprise-secret-1",
    )
    returncode, _, stderr = await _run_cli(env)
    assert returncode == 1
    assert "alembic upgrade head" in stderr
