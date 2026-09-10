"""Redis client (revocation, rate limiting, locks, cache). PostgreSQL stays source of truth."""

from __future__ import annotations

from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> Redis:
    client: Redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return client
