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
    import jwt

    from app.core.config import get_settings

    settings = get_settings()
    forged = jwt.encode(
        {"sub": "x", "type": "access", "iss": settings.jwt_issuer, "aud": settings.jwt_audience},
        "attacker-controlled-secret-key-long-enough-for-hs256",
        algorithm="HS256",
    )
    with pytest.raises(AuthError):
        security.decode_token(forged, security.ACCESS_TYPE)


def test_jwt_tampered_rejected() -> None:
    pair = security.create_token_pair("user-1")
    with pytest.raises(AuthError):
        security.decode_token(pair["access_token"] + "tamper", security.ACCESS_TYPE)


def test_adms_payload_query_params_redact_secrets() -> None:
    from starlette.requests import Request

    from app.adms.router import _safe_query_params

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/iclock/querydata",
            "query_string": b"SN=DEVICE-1&table=userinfo&token=never-store&Password=also-secret",
            "headers": [],
        }
    )
    assert _safe_query_params(request) == {
        "SN": "DEVICE-1",
        "table": "userinfo",
        "token": "***",
        "Password": "***",
    }


def test_device_stats_route_is_not_captured_by_uuid_route() -> None:
    from starlette.routing import Match

    from app.api.v1.devices import router

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/devices/stats/summary",
        "headers": [],
    }
    matched = [route for route in router.routes if route.matches(scope)[0] is Match.FULL]
    assert len(matched) == 1
    assert matched[0].endpoint.__name__ == "summary"
