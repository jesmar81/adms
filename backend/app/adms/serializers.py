"""Wire serializers — exact `text/plain` responses the firmware expects."""

from __future__ import annotations

from typing import TypedDict, Unpack


class SecurityPushConfig(TypedDict):
    server_version: str
    server_name: str
    push_protocol_version: str
    error_delay: int
    request_delay: int
    trans_times: str
    trans_interval: int
    trans_tables: str
    realtime: int
    session_id: str
    timeout_sec: int


def wire_ok() -> str:
    return "OK"


def wire_attlog_ack(count: int) -> str:
    return f"OK: {count}"


def wire_command(protocol_command_id: int, command: str) -> str:
    return f"C:{protocol_command_id}:{command}\n"


def wire_commands(entries: list[tuple[int, str]]) -> str:
    if not entries:
        return wire_ok()
    return "".join(wire_command(cid, cmd) for cid, cmd in entries)


def wire_push_options(serial_number: str, *, trans_flag: str) -> str:
    """Push-upload configuration answered to `GET /iclock/cdata?...&options=all`.

    The firmware polls this handshake expecting its upload knobs
    (TransFlag/Realtime); answering plain `OK` leaves uploads disabled on
    several acc firmwares, so the device never pushes ATTLOG/USERINFO and never
    moves to getrequest/devicecmd.

    Line terminators are CRLF: required by several ZKTeco acc firmwares
    (unverified on our hardware — see docs/ADMS_PROTOCOL.md §26).

    This is the legacy attendance-terminal handshake.  Access-control PUSH
    devices (``DeviceType=acc``) use ``wire_security_push_*`` below instead.
    """
    lines = [
        f"GET OPTION FROM: {serial_number}",
        "Stamp=9999",
        "OpStamp=0",
        "ErrorDelay=60",
        "Delay=30",
        "TransTimes=00:00;14:05",
        "TransInterval=1",
        f"TransFlag={trans_flag}",
        "Realtime=1",
        "Encrypt=0",
        "PushProtVer=3.1.2",
        "PushOptionsFlag=1",
    ]
    return "\r\n".join(lines) + "\r\n"


def wire_registry_code(registry_code: str) -> str:
    """Security PUSH registration acknowledgement for ``DeviceType=acc``."""
    return f"RegistryCode={registry_code}"


def _security_push_lines(
    *,
    server_version: str,
    server_name: str,
    push_protocol_version: str,
    error_delay: int,
    request_delay: int,
    trans_times: str,
    trans_interval: int,
    trans_tables: str,
    realtime: int,
    session_id: str,
    timeout_sec: int,
) -> list[str]:
    """Configuration fields mandated by Security PUSH 3.x."""
    return [
        f"ServerVersion={server_version}",
        f"ServerName={server_name}",
        f"PushProtVer={push_protocol_version}",
        # Some 3.x firmwares use this older spelling in /push responses.
        f"PushVersion={push_protocol_version}",
        f"ErrorDelay={error_delay}",
        f"RequestDelay={request_delay}",
        f"TransTimes={trans_times}",
        f"TransInterval={trans_interval}",
        f"TransTables={trans_tables}",
        f"Realtime={realtime}",
        "PushOptionsFlag=1",
        f"SessionID={session_id}",
        f"TimeoutSec={timeout_sec}",
    ]


def wire_security_push_config(**kwargs: Unpack[SecurityPushConfig]) -> str:
    """Configuration returned by ``/iclock/push`` after ACC registration."""
    return "\r\n".join(_security_push_lines(**kwargs)) + "\r\n"


def wire_security_push_options(*, registry_code: str, **kwargs: Unpack[SecurityPushConfig]) -> str:
    """Configuration returned to a registered ACC device at ``cdata``."""
    lines = ["registry=ok", f"RegistryCode={registry_code}", *_security_push_lines(**kwargs)]
    return "\r\n".join(lines) + "\r\n"
