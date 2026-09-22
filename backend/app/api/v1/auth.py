"""Auth endpoints: login / refresh / logout (Redis revocation, §51)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import deps
from app.api.v1.schemas import LoginIn, RefreshIn, TokenOut
from app.core import security
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthError
from app.core.logging import get_logger
from app.core.ratelimit import hit, redis_or_503
from app.core.revocation import consume_refresh, is_revoked, remember_refresh, revoke
from app.models.user import User
from app.services import audit as audit_svc
from app.services import auth as auth_svc

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("auth")


def _peer_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _account_key(request: Request) -> str:
    try:
        body = await request.json()
        username = str(body.get("username", "")).strip().lower()[:100]
    except Exception:
        username = ""
    return f"{_peer_ip(request)}:{username}"


async def _enforce(request: Request, prefix: str, limit: int, window_s: int, key: str) -> None:
    client = await redis_or_503()
    allowed, retry_after = await hit(client, f"rl:{prefix}:{key}", limit, window_s)
    if not allowed:
        rid = getattr(request.state, "request_id", "")
        raise HTTPException(
            status_code=429,
            detail={
                "error": {"code": "RATE_LIMITED", "message": "Too many requests", "request_id": rid}
            },
            headers={"Retry-After": str(retry_after)},
        )


async def _login_guard(request: Request) -> None:
    settings = get_settings()
    await _enforce(
        request,
        "login:ip",
        settings.ratelimit_login_max_attempts,
        settings.ratelimit_login_window_s,
        _peer_ip(request),
    )
    await _enforce(
        request,
        "login:account",
        settings.ratelimit_login_max_attempts,
        settings.ratelimit_login_window_s,
        await _account_key(request),
    )


async def _refresh_guard(request: Request) -> None:
    settings = get_settings()
    await _enforce(
        request,
        "refresh:ip",
        settings.ratelimit_refresh_max_attempts,
        settings.ratelimit_refresh_window_s,
        _peer_ip(request),
    )


async def _lockout_key(username: str, peer: str) -> str:
    return f"rl:lockout:{username.strip().lower()[:100]}:{peer}"


def _429(request: Request, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "error": {
                "code": "RATE_LIMITED",
                "message": "Too many requests",
                "request_id": getattr(request.state, "request_id", ""),
            }
        },
        headers={"Retry-After": str(retry_after)},
    )


def _503(request: Request | None = None) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Authentication service temporarily unavailable",
                "request_id": getattr(request.state, "request_id", "") if request else "",
            }
        },
    )


async def _is_locked(client: Any, username: str, peer: str) -> tuple[bool, int]:
    """Read the lockout counter WITHOUT incrementing it."""
    settings = get_settings()
    raw = await client.get(await _lockout_key(username, peer))
    try:
        count = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        count = 0
    if count >= settings.ratelimit_lockout_threshold:
        ttl = await client.ttl(await _lockout_key(username, peer))
        return True, ttl if ttl > 0 else settings.ratelimit_lockout_window_s
    return False, 0


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
    ip: str = Depends(deps.client_ip),
    _guard: None = Depends(_login_guard),
) -> TokenOut:
    settings = get_settings()
    peer = _peer_ip(request)
    try:
        client = await redis_or_503()
        locked, retry_after = await _is_locked(client, payload.username, peer)
        if locked:
            log.warning("account_locked", username=payload.username)
            raise _429(request, retry_after)
    except HTTPException:
        raise
    except RedisError as exc:
        raise _503(request) from exc
    try:
        user = await auth_svc.authenticate(session, payload.username, payload.password)
    except AuthError:
        try:
            client = await redis_or_503()
            allowed, retry_after = await hit(
                client,
                await _lockout_key(payload.username, peer),
                settings.ratelimit_lockout_threshold,
                settings.ratelimit_lockout_window_s,
            )
            if not allowed:
                log.warning("account_locked", username=payload.username)
                raise _429(request, retry_after)
        except HTTPException:
            raise
        except RedisError as exc:
            raise _503(request) from exc
        await audit_svc.record(
            session,
            action="login.failed",
            ip_address=ip or None,
            user_agent=request.headers.get("user-agent"),
            request_id=rid,
            metadata={"username": payload.username},
        )
        await session.commit()
        raise
    try:
        client = await redis_or_503()
        await client.delete(await _lockout_key(payload.username, peer))
    except RedisError as exc:
        raise _503(request) from exc
    pair = security.create_token_pair(str(user.id))
    try:
        await remember_refresh(pair["refresh_jti"], str(user.id), settings.jwt_refresh_ttl)
    except RedisError as exc:
        raise _503(request) from exc
    await audit_svc.record(
        session,
        action="login",
        user_id=user.id,
        ip_address=ip or None,
        user_agent=request.headers.get("user-agent"),
        request_id=rid,
    )
    await session.commit()
    return TokenOut(access_token=pair["access_token"], refresh_token=pair["refresh_token"])


@router.get("/me")
async def me(
    user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Current identity + effective permissions (M-07 UI gating; backend still enforces)."""
    from app.api.v1.users import _to_out as _user_out

    return {
        "user": _user_out(user).model_dump(mode="json"),
        "permissions": sorted(await auth_svc.user_permissions(session, user)),
    }


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    payload: RefreshIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    _guard: None = Depends(_refresh_guard),
) -> TokenOut:
    try:
        claims = security.decode_token(payload.refresh_token, security.REFRESH_TYPE)
    except AuthError:
        raise
    try:
        if await is_revoked(claims["jti"]):
            raise AuthError("Token revoked")
        if not await consume_refresh(claims["jti"], claims["sub"]):
            raise AuthError("Refresh session expired or already used")
    except RedisError as exc:
        raise _503(request) from exc
    user = await auth_svc.get_user_by_id(session, claims["sub"])
    if user is None or not user.is_active:
        raise AuthError("Invalid token")
    pair = security.create_token_pair(str(user.id))
    try:
        await remember_refresh(pair["refresh_jti"], str(user.id), get_settings().jwt_refresh_ttl)
    except RedisError as exc:
        raise _503(request) from exc
    return TokenOut(access_token=pair["access_token"], refresh_token=pair["refresh_token"])


@router.post("/logout", status_code=204)
async def logout(
    payload: RefreshIn,
    request: Request,
    user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> None:
    """Terminate the session: revoke BOTH the presenting access token and the
    refresh token (M-01). Either revocation failing closed aborts logout."""
    try:
        claims = security.decode_token(payload.refresh_token, security.REFRESH_TYPE)
        if claims["sub"] == str(user.id):
            await consume_refresh(claims["jti"], str(user.id))
            await revoke(claims["jti"], get_settings().jwt_refresh_ttl)
    except AuthError:
        pass
    except RedisError as exc:
        raise _503(request) from exc
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        try:
            access_claims = security.decode_token(auth_header[7:].strip(), security.ACCESS_TYPE)
            await revoke(access_claims["jti"], get_settings().jwt_access_ttl)
        except AuthError:
            pass
        except RedisError as exc:
            raise _503(request) from exc
    await audit_svc.record(session, action="logout", user_id=user.id, request_id=rid)
    await session.commit()
    return None
