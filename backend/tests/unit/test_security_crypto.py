"""Crypto tests: Argon2id hashing + JWT RS256 issue/verify/reject."""

from __future__ import annotations

import pytest

from app.core import security
from app.core.exceptions import AuthError


def test_argon2id_roundtrip() -> None:
    hashed = security.hash_password("s3cret!")
    assert hashed != "s3cret!"
    assert security.verify_password("s3cret!", hashed)
    assert not security.verify_password("wrong", hashed)


def test_jwt_pair_and_decode() -> None:
    pair = security.create_token_pair("user-1")
    access = security.decode_token(pair["access_token"], security.ACCESS_TYPE)
    refresh = security.decode_token(pair["refresh_token"], security.REFRESH_TYPE)
    assert access["sub"] == "user-1" and access["type"] == "access"
    assert refresh["type"] == "refresh"
    for claim in ("sub", "iat", "exp", "jti", "type", "iss", "aud"):
        assert claim in access


def test_jwt_wrong_type_rejected() -> None:
    pair = security.create_token_pair("user-1")
    with pytest.raises(AuthError):
        security.decode_token(pair["access_token"], security.REFRESH_TYPE)


def test_jwt_algorithm_confusion_rejected() -> None:
    from jose import jwt

    from app.core.config import get_settings

    settings = get_settings()
    forged = jwt.encode(
        {"sub": "x", "type": "access", "iss": settings.jwt_issuer, "aud": settings.jwt_audience},
        "not-a-key",
        algorithm="HS256",
    )
    with pytest.raises(AuthError):
        security.decode_token(forged, security.ACCESS_TYPE)


def test_jwt_tampered_rejected() -> None:
    pair = security.create_token_pair("user-1")
    with pytest.raises(AuthError):
        security.decode_token(pair["access_token"] + "tamper", security.ACCESS_TYPE)
