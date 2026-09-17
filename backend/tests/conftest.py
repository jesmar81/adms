"""Pytest root conftest: env isolation, RSA keys, async DB, app fixtures."""

from __future__ import annotations

import os
import sys
import tempfile

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_tmp = tempfile.mkdtemp(prefix="zkteco-test-")
_db_path = os.path.join(_tmp, "test.db")
_priv = os.path.join(_tmp, "jwt_priv.pem")
_pub = os.path.join(_tmp, "jwt_pub.pem")

os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_db_path}")
os.environ.setdefault("JWT_PRIVATE_KEY_FILE", _priv)
os.environ.setdefault("JWT_PUBLIC_KEY_FILE", _pub)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")


def _write_test_keys() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with open(_priv, "wb") as fh:
        fh.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    with open(_pub, "wb") as fh:
        fh.write(
            key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )


_write_test_keys()

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.models.device  # noqa: E402,F401
import app.models.hr  # noqa: E402,F401
import app.models.user  # noqa: E402,F401
from app.core.database import reset_engine_for_tests  # noqa: E402
from app.core.redis import get_redis  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.base import Base  # noqa: E402

reset_engine_for_tests()
_test_engine = create_async_engine(f"sqlite+aiosqlite:///{_db_path}")
_test_sessions = async_sessionmaker(_test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch):  # type: ignore[no-untyped-def]
    """Hermetic Redis for every test (fakeredis, per-test isolated server).

    Set ZKTECO_USE_REAL_REDIS=1 (CI postgres job) to exercise the real
    shared Redis service instead.
    """
    if os.environ.get("ZKTECO_USE_REAL_REDIS") == "1":
        get_redis.cache_clear()
        yield None
        get_redis.cache_clear()
        return
    from fakeredis.aioredis import FakeRedis, FakeServer

    server = FakeServer()

    def _factory(cls, *args, **kwargs):  # type: ignore[no-untyped-def]
        return FakeRedis(server=server, decode_responses=True)

    monkeypatch.setattr("redis.asyncio.Redis.from_url", classmethod(_factory))
    get_redis.cache_clear()
    yield server
    get_redis.cache_clear()


def _pg_url() -> str | None:
    return os.environ.get("ZKTECO_TEST_PG_URL")


async def _run_blocking(fn, *args):  # type: ignore[no-untyped-def]
    import asyncio

    return await asyncio.to_thread(fn, *args)


@pytest_asyncio.fixture(scope="session")
async def pg_migrated_url():  # type: ignore[no-untyped-def]
    """Migrate once per session with `alembic upgrade head` (H-03 proof).

    Returns the PG URL. Holds no loop-bound resources, so function-scoped
    engines created from it work in any test loop.
    """
    url = _pg_url()
    if not url:
        pytest.skip("ZKTECO_TEST_PG_URL not set — postgres integration tests need PG")
    try:
        from alembic.config import Config

        from alembic import command as alembic_command

        old = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = url
        try:
            cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
            await _run_blocking(alembic_command.upgrade, cfg, "head")
        finally:
            if old is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = old
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    return url


@pytest_asyncio.fixture
async def pg_engine(pg_migrated_url):  # type: ignore[no-untyped-def]
    """Function-scoped PG engine (fresh pool in the test's event loop)."""
    import sqlalchemy
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(pg_migrated_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unreachable: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine):  # type: ignore[no-untyped-def]
    """Isolated PG session: TRUNCATE all tables before each test."""
    import sqlalchemy
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with pg_engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(sqlalchemy.text(f"TRUNCATE {tables} CASCADE"))
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


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
async def db_session():  # type: ignore[no-untyped-def]
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Full isolation: wipe rows (fixtures run against one shared sqlite file).
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    async with _test_sessions() as session:
        yield session
        await session.rollback()
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app_client(db_session):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from app.core.database import get_db

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def settings():  # type: ignore[no-untyped-def]
    return get_settings()
