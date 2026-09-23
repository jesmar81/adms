"""H-02 seed tests: first-admin bootstrap via env (idempotent, audited)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import func, select

from app.core import security
from app.core.constants import DEFAULT_ROLES, PERMISSIONS
from app.models.user import AuditLog, Role, User
from app.services.bootstrap import (
    ensure_roles_permissions,
    ensure_superuser,
    validate_admin_input,
)

pytestmark = pytest.mark.pg


async def test_ensure_superuser_creates_admin(pg_session) -> None:  # type: ignore[no-untyped-def]
    user, created = await ensure_superuser(
        pg_session, username="root", email="root@example.com", password="enterprise-secret-1"
    )
    await pg_session.commit()
    assert created is True
    assert user.is_superuser is True and user.is_active is True
    assert [r.name for r in user.roles] == ["admin"]
    assert security.verify_password("enterprise-secret-1", user.password_hash)
    assert "enterprise-secret-1" not in user.password_hash
    admin_perms = {p.code for r in user.roles for p in r.permissions}
    assert admin_perms == set(PERMISSIONS)
    audit = await pg_session.execute(select(AuditLog).where(AuditLog.action == "user.create"))
    entries = audit.scalars().all()
    assert len(entries) == 1
    assert entries[0].meta == {"username": "root", "via": "seed"}
    assert entries[0].user_id == user.id


async def test_ensure_superuser_leaves_existing_untouched(
    pg_session,
) -> None:  # type: ignore[no-untyped-def]
    plain = User(
        username="root",
        email="root@example.com",
        password_hash=security.hash_password("old-password-1"),
        is_active=True,
    )
    pg_session.add(plain)
    await pg_session.commit()
    user, created = await ensure_superuser(
        pg_session, username="root", email="other@example.com", password="enterprise-secret-1"
    )
    await pg_session.commit()
    assert created is False
    assert user.id == plain.id
    assert user.is_superuser is False  # no silent escalation
    assert security.verify_password("old-password-1", user.password_hash)
    count = await pg_session.scalar(select(func.count()).select_from(User))
    assert count == 1


def test_validate_admin_input_rejects() -> None:
    with pytest.raises(ValueError, match="username"):
        validate_admin_input("ab", "a@b.co", "long-password-enterprise-1")
    with pytest.raises(ValueError, match="email"):
        validate_admin_input("abc", "not-an-email", "long-password-enterprise-1")
    with pytest.raises(ValueError, match="password"):
        validate_admin_input("abc", "a@b.co", "short")
    validate_admin_input("abc", "a@b.co", "long-password-enterprise-1")  # no raise


async def test_ensure_roles_permissions_idempotent(
    pg_session,
) -> None:  # type: ignore[no-untyped-def]
    await ensure_roles_permissions(pg_session)
    await pg_session.commit()
    await ensure_roles_permissions(pg_session)
    await pg_session.commit()
    role_names = set((await pg_session.execute(select(Role.name))).scalars().all())
    assert role_names == set(DEFAULT_ROLES)


async def test_seed_main_bootstraps_admin(pg_session, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.seed import main

    monkeypatch.setattr(settings, "database_url", os.environ["ZKTECO_TEST_PG_URL"])
    monkeypatch.setenv("ZKTECO_ADMIN_USERNAME", "seedadmin")
    monkeypatch.setenv("ZKTECO_ADMIN_EMAIL", "seed@example.com")
    monkeypatch.setenv("ZKTECO_ADMIN_PASSWORD", "seed-password-1")
    await main()
    await main()  # rerun: idempotent, no duplicates
    count = await pg_session.scalar(select(func.count()).select_from(User))
    assert count == 1
    user = await pg_session.scalar(select(User).where(User.username == "seedadmin"))
    assert user is not None and user.is_superuser is True
    assert security.verify_password("seed-password-1", user.password_hash)


async def test_seed_main_without_env_creates_no_users(pg_session, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.seed import main

    monkeypatch.setattr(settings, "database_url", os.environ["ZKTECO_TEST_PG_URL"])
    for var in ("ZKTECO_ADMIN_USERNAME", "ZKTECO_ADMIN_EMAIL", "ZKTECO_ADMIN_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    await main()
    count = await pg_session.scalar(select(func.count()).select_from(User))
    assert count == 0
    role_names = set((await pg_session.execute(select(Role.name))).scalars().all())
    assert role_names == set(DEFAULT_ROLES)


async def test_seed_main_invalid_admin_exits_2(pg_session, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.seed import main

    monkeypatch.setattr(settings, "database_url", os.environ["ZKTECO_TEST_PG_URL"])
    monkeypatch.setenv("ZKTECO_ADMIN_USERNAME", "x")
    monkeypatch.setenv("ZKTECO_ADMIN_EMAIL", "bad")
    monkeypatch.setenv("ZKTECO_ADMIN_PASSWORD", "y")
    with pytest.raises(SystemExit) as exc:
        await main()
    assert exc.value.code == 2
    role_names = set((await pg_session.execute(select(Role.name))).scalars().all())
    assert role_names == set(DEFAULT_ROLES)
