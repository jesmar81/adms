"""Distributed rate limiting (Redis) + fail-closed policy for auth (§52, H-01).

- Primary mechanism is Redis so limits hold across workers/containers/instances.
- Auth endpoints (login/refresh/authenticated calls) are FAIL-CLOSED: if Redis
  is unreachable the request is rejected with 503 instead of running unprotected.
- ADMS device endpoints are FAIL-OPEN by explicit trade-off: attendance
  ingestion availability outranks throttling, and devices cannot authenticate
  any other way. Floods are still logged. See docs/SECURITY.md.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.core.redis import get_redis

log = get_logger("ratelimit")


async def hit(redis: Redis, key: str, limit: int, window_s: int) -> tuple[bool, int]:
    """Increment the fixed-window counter. Returns (allowed, retry_after_s).

    INCR + conditional EXPIRE via pipeline. The only non-atomic corner is a
    crash between the two commands, which at worst leaks one key until it is
    overwritten — no over-admission, since INCR is authoritative.
    """
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    count_obj, ttl_obj = await pipe.execute()
    count = int(count_obj)
    ttl = int(ttl_obj)
    if count == 1 or ttl < 0:
        await redis.expire(key, window_s)
        ttl = window_s
    if count <= limit:
        return True, 0
    retry_after = ttl if ttl > 0 else window_s
    return False, retry_after


def _429_admin(request: Request, retry_after: int) -> HTTPException:
    rid = getattr(request.state, "request_id", "")
    return HTTPException(
        status_code=429,
        detail={
            "error": {"code": "RATE_LIMITED", "message": "Too many requests", "request_id": rid}
        },
        headers={"Retry-After": str(retry_after)},
    )


async def redis_or_503() -> Redis:
    """Return a live Redis client or raise 503 (fail-closed for auth paths)."""
    try:
        client = get_redis()
        await client.ping()
    except RedisError as exc:
        log.error("redis_unavailable_fail_closed", error=str(exc)[:200])
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Authentication service temporarily unavailable",
                    "request_id": "",
                }
            },
        ) from exc
    return client


async def check_adms_limit(request: Request, serial: str, endpoint: str) -> bool:
    """Fail-open per-device + per-IP throttle for ADMS. Returns True if allowed."""
    from app.core.config import get_settings

    settings = get_settings()
    try:
        client = get_redis()
        device_key = f"rl:adms:{endpoint}:{serial}"
        allowed_device, _ = await hit(
            client,
            device_key,
            settings.ratelimit_adms_device_max,
            settings.ratelimit_adms_device_window_s,
        )
        if not allowed_device:
            log.warning("adms_rate_limited", serial=serial, endpoint=endpoint)
            return False
        peer = request.client.host if request.client else "unknown"
        ip_key = f"rl:adms:ip:{endpoint}:{peer}"
        allowed_ip, _ = await hit(
            client, ip_key, settings.ratelimit_adms_ip_max, settings.ratelimit_adms_ip_window_s
        )
        if not allowed_ip:
            log.warning("adms_ip_rate_limited", ip=peer, endpoint=endpoint)
            return False
        return True
    except RedisError as exc:
        log.warning("adms_ratelimit_redis_down_fail_open", error=str(exc)[:200])
        return True
