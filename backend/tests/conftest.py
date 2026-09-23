"""Pytest fixtures backed exclusively by migrated PostgreSQL and real Redis."""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_test_pg_url = os.environ.get("ZKTECO_TEST_PG_URL")
if not _test_pg_url:
    raise RuntimeError("Set ZKTECO_TEST_PG_URL to a dedicated PostgreSQL test database")
_parsed_pg_url = make_url(_test_pg_url)
if _parsed_pg_url.get_backend_name() != "postgresql":
    raise RuntimeError("ZKTECO_TEST_PG_URL must use PostgreSQL")
if "test" not in (_parsed_pg_url.database or "").lower():
    raise RuntimeError(
        "ZKTECO_TEST_PG_URL database name must contain 'test' (suite truncates tables)"
    )

_test_redis_url = os.environ.get("ZKTECO_TEST_REDIS_URL")
if not _test_redis_url:
    raise RuntimeError("Set ZKTECO_TEST_REDIS_URL to a dedicated Redis test database")
_parsed_redis_url = urlsplit(_test_redis_url)
if _parsed_redis_url.scheme not in {"redis", "rediss"} or _parsed_redis_url.path != "/15":
    raise RuntimeError("ZKTECO_TEST_REDIS_URL must point to Redis database 15")

# Never let .env or a developer's normal DATABASE_URL redirect destructive test
# setup to an application database. Redis tests are pinned to the dedicated DB.
os.environ["DATABASE_URL"] = _test_pg_url
os.environ["REDIS_URL"] = _test_redis_url
# Existing protocol tests exercise device-originated discovery. Production is
# secure-by-default and provisions serials explicitly through the admin API.
os.environ.setdefault("ZKTECO_AUTO_REGISTER_UNKNOWN", "true")

_key_dir = tempfile.mkdtemp(prefix="zkteco-test-keys-")
_priv = Path(_key_dir) / "jwt_priv.pem"
_pub = Path(_key_dir) / "jwt_pub.pem"
os.environ["JWT_PRIVATE_KEY_FILE"] = str(_priv)
os.environ["JWT_PUBLIC_KEY_FILE"] = str(_pub)


def _write_test_keys() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _priv.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    _pub.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


_write_test_keys()

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: E402

import app.models.device  # noqa: E402,F401
import app.models.hr  # noqa: E402,F401
import app.models.user  # noqa: E402,F401
from app.core.redis import get_redis  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.base import Base  # noqa: E402


async def _run_blocking(fn: Callable[..., object], *args: object) -> object:
    import asyncio

    return await asyncio.to_thread(fn, *args)


@pytest_asyncio.fixture(scope="session")
async def pg_migrated_url() -> str:
    """Run the actual Alembic chain once before any test uses PostgreSQL."""
    from alembic.config import Config

    from alembic import command as alembic_command

    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    try:
        await _run_blocking(alembic_command.upgrade, config, "head")
    except Exception as exc:
        pytest.fail(f"Could not migrate the PostgreSQL test database: {exc}")
    return _test_pg_url


@pytest_asyncio.fixture
async def pg_engine(pg_migrated_url: str):
    """Function-scoped engine so every test gets a pool in its own loop."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(pg_migrated_url)
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
    except Exception:
        await engine.dispose()
        raise
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine):  # type: ignore[no-untyped-def]
    """Isolated PostgreSQL session; all migrated application tables are cleared."""
    import sqlalchemy

    async with pg_engine.begin() as conn:
        tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
        await conn.execute(sqlalchemy.text(f"TRUNCATE {tables} CASCADE"))
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(autouse=True)
async def real_redis():  # type: ignore[no-untyped-def]
    """Use and clear real Redis DB 15 for each test; no in-memory substitute."""
    from redis.exceptions import RedisError

    get_redis.cache_clear()
    client = get_redis()
    try:
        await client.ping()
        await client.flushdb()
    except RedisError as exc:
        await client.aclose()
        get_redis.cache_clear()
        pytest.fail(f"Real Redis test database is unavailable: {exc}")
    yield client
    cached_client = get_redis()
    if cached_client is not client:
        await cached_client.aclose()
    await client.flushdb()
    await client.aclose()
    get_redis.cache_clear()


@pytest_asyncio.fixture
async def db_session(pg_session):  # type: ignore[no-untyped-def]
    """Compatibility name used by existing tests, now backed only by PostgreSQL."""
    yield pg_session


@pytest_asyncio.fixture
async def pg_client(pg_session):  # type: ignore[no-untyped-def]
    from httpx import ASGITransport, AsyncClient

    from app.core.database import get_db

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        yield pg_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def app_client(db_session):  # type: ignore[no-untyped-def]
    """Async app client sharing the test's PostgreSQL transaction/session."""
    from httpx import ASGITransport, AsyncClient

    from app.core.database import get_db

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unmigrated_pg_url(pg_migrated_url: str):
    """An isolated, empty PostgreSQL database for CLI migration-guard tests."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    database_name = f"adms_unmigrated_test_{uuid.uuid4().hex[:12]}"
    admin_url = make_url(pg_migrated_url).set(database="postgres")
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{database_name}"'))
        yield (
            make_url(pg_migrated_url)
            .set(database=database_name)
            .render_as_string(hide_password=False)
        )
    finally:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        await admin_engine.dispose()


@pytest_asyncio.fixture
async def postgres_failure_trigger(pg_engine, pg_session):  # type: ignore[no-untyped-def]
    """Install a real PostgreSQL trigger to exercise persistence failure paths."""
    from sqlalchemy import text

    allowed_tables = {table.name for table in Base.metadata.sorted_tables}
    objects: list[tuple[str, str]] = []

    async def install(table: str, operation: str = "INSERT") -> None:
        allowed_operations = {"INSERT", "UPDATE", "UPDATE OF last_registry_at"}
        if table not in allowed_tables or operation not in allowed_operations:
            raise ValueError("Unsupported failure trigger target")
        suffix = uuid.uuid4().hex
        function_name = f"test_failure_{suffix}"
        trigger_name = f"test_failure_{suffix}"
        async with pg_engine.begin() as conn:
            await conn.execute(
                text(
                    f"CREATE FUNCTION public.{function_name}() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test persistence failure'; "
                    "END; $$"
                )
            )
            await conn.execute(
                text(
                    f"CREATE TRIGGER {trigger_name} BEFORE {operation} ON public.{table} "
                    f"FOR EACH ROW EXECUTE FUNCTION public.{function_name}()"
                )
            )
        objects.append(("", function_name))
        objects.append((table, trigger_name))

    yield install
    await pg_session.rollback()
    await pg_session.close()
    async with pg_engine.begin() as conn:
        for table, name in reversed(objects):
            if table:
                await conn.execute(text(f"DROP TRIGGER IF EXISTS {name} ON public.{table}"))
            else:
                await conn.execute(text(f"DROP FUNCTION IF EXISTS public.{name}()"))


@pytest.fixture
def settings():  # type: ignore[no-untyped-def]
    return get_settings()
