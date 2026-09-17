"""USERINFO / KV / registry / command-result parser tests."""

from __future__ import annotations

from app.adms.parser import (
    parse_command_results,
    parse_device_info,
    parse_info_command_response,
    parse_kv_pairs,
    parse_registry_body,
    parse_userinfo,
    trim_tilde_prefix,
)


def test_userinfo_basic() -> None:
    body = (
        "PIN=1\tName=John\tPrivilege=0\tCard=\tPassword=\n"
        "PIN=2\tName=Ana\tPrivilege=14\tCard=99\tPassword="
    )
    users, stats = parse_userinfo(body, "S1")
    assert len(users) == 2 and stats.skipped == 0
    assert users[0].pin == "1" and users[0].name == "John"
    assert users[1].privilege == 14 and users[1].card == "99"


def test_userinfo_without_pin_skipped() -> None:
    users, stats = parse_userinfo("Name=NoPin\tPrivilege=0", "S1")
    assert users == [] and stats.skipped == 1


def test_registry_tilde_prefix() -> None:
    info = parse_registry_body("~DeviceName=SpeedFace,~FWVersion=Ver 1.1.17,~MACAddress=AA:BB")
    assert info == {"DeviceName": "SpeedFace", "FWVersion": "Ver 1.1.17", "MACAddress": "AA:BB"}


def test_device_info_newline_kv() -> None:
    info = parse_device_info("FWVersion=Ver 8.1.1\nDeviceName=TestDevice\nIPAddress=192.168.1.100")
    assert info["DeviceName"] == "TestDevice"


def test_info_command_response_normalizes_real_v5l_inventory() -> None:
    info = parse_info_command_response(
        "ID=10&Return=0&CMD=INFO\n~DeviceName=SpeedFace-V5L\n"
        "MAC=00:17:61:11:cf:40\nFWVersion=ZAM230-NF50VA-Ver1.1.9\n~Platform=ZAM230_TFT"
    )
    assert info["DeviceName"] == "SpeedFace-V5L"
    assert info["MACAddress"] == "00:17:61:11:cf:40"
    assert info["Platform"] == "ZAM230_TFT"


def test_kv_ignores_lines_without_equals() -> None:
    assert parse_kv_pairs("foo\nA=B") == {"A": "B"}
    assert trim_tilde_prefix("~~X") == "X"


def test_command_results_batched() -> None:
    results = parse_command_results("ID=1&Return=0&CMD=INFO\nID=2&Return=1&CMD=CHECK\n", "S1")
    assert [(r.protocol_command_id, r.return_code, r.is_success) for r in results] == [
        (1, 0, True),
        (2, 1, False),
    ]


def test_command_results_shell_multiline() -> None:
    results = parse_command_results("ID=32\nReturn=0\nCMD=Shell\nContent=out\n", "S1")
    assert len(results) == 1 and results[0].protocol_command_id == 32


def test_command_results_unparseable_id_skipped() -> None:
    results = parse_command_results("ID=abc&Return=0&CMD=INFO", "S1")
    assert results == []
