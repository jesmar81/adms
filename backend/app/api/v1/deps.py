"""Shared admin dependencies: request_id, current user, permission guard."""

from __future__ import annotations

import ipaddress
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.database import get_db
from app.core.revocation import is_revoked
from app.models.user import User
from app.services import auth as auth_svc

bearer = HTTPBearer(auto_error=False)


async def request_id(request: Request) -> str:
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    return rid


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        claims = security.decode_token(credentials.credentials, security.ACCESS_TYPE)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token") from None
    try:
        revoked = await is_revoked(claims["jti"])
    except RedisError as exc:
        # Fail closed: without revocation checks we cannot trust tokens.
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Authentication service temporarily unavailable",
                    "request_id": getattr(request.state, "request_id", ""),
                }
            },
        ) from exc
    if revoked:
        raise HTTPException(status_code=401, detail="Token revoked")
    user = await auth_svc.get_user_by_id(session, claims["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    request.state.user = user
    return user


def require_permission(code: str):  # type: ignore[no-untyped-def]
    async def guard(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> User:
        if user.is_superuser:
            return user
        perms = await auth_svc.user_permissions(session, user)
        if code not in perms:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return guard


def _peer_trusted(peer: str) -> bool:
    for entry in get_settings().trusted_proxies():
        try:
            if "/" in entry:
                if ipaddress.ip_address(peer) in ipaddress.ip_network(entry, strict=False):
                    return True
            elif peer == entry:
                return True
        except ValueError:
            continue
    return False


async def client_ip(request: Request, x_forwarded_for: str | None = Header(default=None)) -> str:
    """Client IP for audit/rate-limit keys. X-Forwarded-For is honored ONLY
    when the direct peer is a configured trusted proxy (L-04)."""
    peer = request.client.host if request.client else ""
    if x_forwarded_for and peer and _peer_trusted(peer):
        return x_forwarded_for.split(",")[0].strip()
    return peer
