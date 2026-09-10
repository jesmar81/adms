"""Gap-closing tests: builders, validators, security edges, config, revocation."""

from __future__ import annotations

import pytest

from app.adms.commands import CommandBuilder, build_command
from app.adms.validators import check_body_size
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthError


def test_check_body_size() -> None:
    assert check_body_size(b"abc", 10)
    assert not check_body_size(b"a" * 11, 10)


def test_build_command_all_types() -> None:
    assert build_command("LOG")[1] == "LOG"
    assert build_command("CHECK")[1] == "CHECK"
    ctype, wire = build_command("UPDATE_USERINFO", {"pin": "9", "name": "N"})
    assert "PIN=9" in wire and ctype.value == "UPDATE_USERINFO"
    assert build_command("DELETE_USERINFO", {"pin": "9"})[1] == "DATA DELETE USERINFO PIN=9"
    assert CommandBuilder.log()[1] == "LOG"
    assert CommandBuilder.query_userinfo()[1] == "DATA QUERY USERINFO"
    with pytest.raises(Exception, match="pin is required"):
        CommandBuilder.update_userinfo(pin="", name="x")
    with pytest.raises(Exception, match="pin is required"):
        CommandBuilder.delete_userinfo(pin="")


def test_verify_password_garbage_hash() -> None:
    from app.core import security

    assert not security.verify_password("x", "not-a-valid-hash")


def test_create_token_without_keys_raises(settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core import security

    monkeypatch.setattr(settings, "jwt_private_key", "")
    monkeypatch.setattr(settings, "jwt_private_key_file", "/nonexistent-xyz.pem")
    monkeypatch.setattr(settings, "jwt_public_key", "")
    monkeypatch.setattr(settings, "jwt_public_key_file", "/nonexistent-xyz.pem")
    with pytest.raises(AuthError):
        security.create_token_pair("u1")
    with pytest.raises(AuthError):
        security.decode_token("whatever", security.ACCESS_TYPE)


def test_load_rsa_keys_from_files(tmp_path) -> None:  # type: ignore[no-untyped-def]
    priv = tmp_path / "priv.pem"
    pub = tmp_path / "pub.pem"
    priv.write_text("PRIV")
    pub.write_text("PUB")
    settings = Settings(jwt_private_key_file=str(priv), jwt_public_key_file=str(pub))
    assert settings.load_rsa_keys() == ("PRIV", "PUB")
    missing = Settings(
        jwt_private_key_file="/nonexistent-a.pem", jwt_public_key_file="/nonexistent-b.pem"
    )
    assert missing.load_rsa_keys() == ("", "")


def test_settings_singleton_defaults() -> None:
    settings = get_settings()
    assert settings.zkteco_max_body_size == 10 * 1024 * 1024
    assert settings.zkteco_online_threshold == 120
