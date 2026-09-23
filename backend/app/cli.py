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

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.bootstrap import ensure_superuser, validate_admin_input


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
    import app.models.hr  # noqa: F401 (register group relationship targets)
    from app.core.config import get_settings

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
    try:
        validate_admin_input(username, email, password)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
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
        _, created = await ensure_superuser(
            session, username=username, email=email, password=password, via="cli"
        )
        if not created:
            print(f"error: username '{username}' already exists", file=sys.stderr)
            await engine.dispose()
            return 1
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
