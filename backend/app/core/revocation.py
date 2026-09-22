"""Token revocation over shared Redis (no local fallback).

There is intentionally NO process-memory fallback: a fallback would silently
stop working across workers/hosts and create a false sense of security (M-01).
Callers decide the policy — auth paths fail closed (503), see core/ratelimit.
"""

from __future__ import annotations

import hmac

from app.core.redis import get_redis


async def revoke(jti: str, ttl_seconds: int) -> None:
    await get_redis().set(f"revoked:{jti}", "1", ex=ttl_seconds)


async def is_revoked(jti: str) -> bool:
    return bool(await get_redis().exists(f"revoked:{jti}"))


async def remember_refresh(jti: str, user_id: str, ttl_seconds: int) -> None:
    await get_redis().setex(f"refresh:{jti}", ttl_seconds, user_id)


async def consume_refresh(jti: str, user_id: str) -> bool:
    """Atomically consume one refresh session.

    Redis is the authoritative session allow-list. ``GETDEL`` makes rotation
    single-use even when two requests present the same token concurrently and
    fails closed after Redis data loss instead of resurrecting old JWTs.
    """
    stored = await get_redis().getdel(f"refresh:{jti}")
    if stored is None:
        return False
    if isinstance(stored, bytes):
        stored = stored.decode("utf-8", errors="replace")
    return hmac.compare_digest(str(stored), user_id)
