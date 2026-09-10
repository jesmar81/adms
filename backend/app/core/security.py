"""Password hashing (Argon2id) + JWT RS256 issue/verify."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import AuthError

ALGORITHM = "RS256"
ACCESS_TYPE = "access"
REFRESH_TYPE = "refresh"

_ph = PasswordHasher()  # defaults: Argon2id


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def _utcnow() -> datetime:
    return datetime.now(UTC)


def create_token(subject: str, token_type: str, ttl_seconds: int) -> tuple[str, str]:
    """Return (token, jti)."""
    settings = get_settings()
    private_key, _ = settings.load_rsa_keys()
    if not private_key:
        raise AuthError("JWT signing key not configured")
    now = _utcnow()
    jti = str(uuid.uuid4())
    claims = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "jti": jti,
        "type": token_type,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(claims, private_key, algorithm=ALGORITHM), jti


def create_token_pair(subject: str) -> dict[str, str]:
    settings = get_settings()
    access, access_jti = create_token(subject, ACCESS_TYPE, settings.jwt_access_ttl)
    refresh, refresh_jti = create_token(subject, REFRESH_TYPE, settings.jwt_refresh_ttl)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "access_jti": access_jti,
        "refresh_jti": refresh_jti,
    }


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    _, public_key = settings.load_rsa_keys()
    if not public_key:
        raise AuthError("JWT verification key not configured")
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=[ALGORITHM],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except JWTError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc
    if claims.get("type") != expected_type:
        raise AuthError("Unexpected token type")
    if not claims.get("sub") or not claims.get("jti"):
        raise AuthError("Token missing required claims")
    return claims
