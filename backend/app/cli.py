"""Administrative CLI (H-02). Run from `backend/`::

    python -m app.cli createsuperuser [--username U] [--email E] [--no-input]

Password is read via getpass prompt or ``ZKTECO_ADMIN_PASSWORD`` (never a CLI
argument, never logged). Requires an Alembic-migrated database — this tool
never creates schema (H-03: no ``create_all`` substitute in production).
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

ADMIN_ROLE = "admin"


def _read(value: str | None, env: str, prompt: str, *, secret: bool = False) -> str:
    if value:
        return value
    from_env = os.environ.get(env, "")
    if from_env:
        return from_env
    if secret:
        return getpass.getpass(prompt)
    return input(prompt)


async def createsuperuser(username: str | None, email: str | None, *, no_input: bool) -> int:
    import app.models.device  # noqa: F401  (register all tables for FK checks)
    from app.core.config import get_settings
    from app.core.constants import PERMISSIONS
    from app.core.security import hash_password
    from app.models.user import Permission, Role, User
    from app.services import audit as audit_svc

    if no_input:
        username = username or os.environ.get("ZKTECO_ADMIN_USERNAME", "")
        email = email or os.environ.get("ZKTECO_ADMIN_EMAIL", "")
        password = os.environ.get("ZKTECO_ADMIN_PASSWORD", "")
        if not username or not email or not password:
            print(
                "error: --no-input requires --username/--email or "
                "ZKTECO_ADMIN_USERNAME/EMAIL/PASSWORD",
                file=sys.stderr,
            )
            return 2
    else:
        username = _read(username, "ZKTECO_ADMIN_USERNAME", "Username: ")
        email = _read(email, "ZKTECO_ADMIN_EMAIL", "Email: ")
        password = _read(None, "ZKTECO_ADMIN_PASSWORD", "Password: ", secret=True)
        if not password:
            print("error: password must not be empty", file=sys.stderr)
            return 2
    if "@" not in email:
        print("error: invalid email address", file=sys.stderr)
        return 2
    if len(password) < 10:
        print("error: password must be at least 10 characters", file=sys.stderr)
        return 2

    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    def _has_users_table(conn) -> bool:  # type: ignore[no-untyped-def]
        return bool(inspect(conn).has_table("users"))

    async with engine.connect() as conn:
        has_tables = await conn.run_sync(_has_users_table)
    if not has_tables:
        print(
            "error: 'users' table missing — run `alembic upgrade head` first",
            file=sys.stderr,
        )
        await engine.dispose()
        return 1

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        existing = await session.scalar(
            select(func.count()).select_from(User).where(User.username == username)
        )
        if existing:
            print(f"error: username '{username}' already exists", file=sys.stderr)
            await engine.dispose()
            return 1
        for code in PERMISSIONS:
            if await session.scalar(select(Permission).where(Permission.code == code)) is None:
                session.add(
                    Permission(
                        id=uuid.uuid4(),
                        code=code,
                        description=code,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
        await session.flush()
        role = await session.scalar(
            select(Role).options(selectinload(Role.permissions)).where(Role.name == ADMIN_ROLE)
        )
        if role is None:
            role = Role(
                id=uuid.uuid4(),
                name=ADMIN_ROLE,
                description="Full access",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(role)
            await session.flush()
            await session.refresh(role, attribute_names=["permissions"])
        result = await session.execute(select(Permission))
        role.permissions = list(result.scalars().all())
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_active=True,
            is_superuser=True,
        )
        user.roles = [role]
        session.add(user)
        await session.flush()
        await audit_svc.record(
            session,
            action="user.create",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            metadata={"username": username, "via": "cli"},
        )
        await session.commit()
    await engine.dispose()
    print(f"superuser '{username}' created")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli", description="ZKTeco ADMS admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("createsuperuser", help="Create a superuser (audited)")
    create.add_argument("--username", default=None)
    create.add_argument("--email", default=None)
    create.add_argument(
        "--no-input", action="store_true", help="Read all values from args/env, never prompt"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "createsuperuser":
        return asyncio.run(createsuperuser(args.username, args.email, no_input=args.no_input))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
