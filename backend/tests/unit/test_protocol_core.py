"""Validators, command builder, wire serializers, online-status tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.adms.commands import CommandBuilder, CommandType, build_command
from app.adms.serializers import wire_attlog_ack, wire_command, wire_commands, wire_ok
from app.adms.validators import validate_serial_number
from app.core.constants import GET_OPTION_KEYS
from app.core.exceptions import InvalidCommandError


def test_serial_valid() -> None:
    assert validate_serial_number("ABC-123_def")


def test_serial_rejects_bad() -> None:
    assert not validate_serial_number("")
    assert not validate_serial_number("has space")
    assert not validate_serial_number("a" * 65)
    assert not validate_serial_number("a;b")
    assert not validate_serial_number("x\nx")


def test_command_builder_user_add_format() -> None:
    ctype, wire = CommandBuilder.update_userinfo(pin="1001", name="John", privilege=0, card="5")
    assert ctype is CommandType.UPDATE_USERINFO
    assert wire == "DATA UPDATE USERINFO PIN=1001\tName=John\tPrivilege=0\tCard=5"


def test_command_builder_delete_format() -> None:
    _, wire = CommandBuilder.delete_userinfo(pin="1001")
    assert wire == "DATA DELETE USERINFO PIN=1001"


def test_command_builder_get_option_whitelist() -> None:
    _, wire = CommandBuilder.get_option("DeviceName")
    assert wire == "GET OPTION FROM DeviceName"
    with pytest.raises(InvalidCommandError):
        CommandBuilder.get_option("Nope")


def test_command_builder_rejects_crlf() -> None:
    with pytest.raises(InvalidCommandError):
        CommandBuilder.update_userinfo(pin="1\n2", name="x")
    with pytest.raises(InvalidCommandError):
        CommandBuilder.delete_userinfo(pin="1\r")


def test_command_builder_privilege_range() -> None:
    with pytest.raises(InvalidCommandError):
        CommandBuilder.update_userinfo(pin="1", name="x", privilege=99)


def test_build_command_dispatch() -> None:
    assert build_command("INFO")[1] == "INFO"
    assert build_command("QUERY_USERINFO")[1] == "DATA QUERY USERINFO"
    assert build_command("GET_OPTION", {"key": "FWVersion"})[1] == "GET OPTION FROM FWVersion"
    with pytest.raises(ValueError, match="not a valid CommandType"):
        build_command("SHELL", {"command": "rm -rf /"})


def test_get_option_keys_documented() -> None:
    assert GET_OPTION_KEYS == frozenset(
        {
            "DeviceName",
            "FWVersion",
            "IPAddress",
            "MACAddress",
            "Platform",
            "WorkCode",
            "LockCount",
            "UserCount",
            "FPCount",
            "AttLogCount",
            "FaceCount",
            "TransactionCount",
            "MaxUserCount",
            "MaxAttLogCount",
            "MaxFingerCount",
            "MaxFaceCount",
        }
    )


def test_wire_formats() -> None:
    assert wire_ok() == "OK"
    assert wire_attlog_ack(2) == "OK: 2"
    assert wire_command(7, "CHECK") == "C:7:CHECK\n"
    assert wire_commands([]) == "OK"
    assert wire_commands([(1, "INFO"), (2, "CHECK")]) == "C:1:INFO\nC:2:CHECK\n"


def test_derived_status_online_offline_stale() -> None:
    from app.models.device import Device
    from app.services import device as device_svc

    now = datetime.now(UTC)
    d = Device(serial_number="S1", status="unknown", options={}, extra_metadata={})
    assert device_svc.derived_status(d, now=now) == "unknown"
    d.last_activity_at = now
    assert device_svc.derived_status(d, now=now) == "online"
    d.last_activity_at = now - timedelta(seconds=1000)
    assert device_svc.derived_status(d, now=now) == "offline"
    d.last_activity_at = now - timedelta(seconds=100000)
    assert device_svc.derived_status(d, now=now) == "stale"
    d.status = "disabled"
    assert device_svc.derived_status(d, now=now) == "disabled"
