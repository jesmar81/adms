"""Wire serializers — exact `text/plain` responses the firmware expects."""

from __future__ import annotations


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

    `trans_flag` bit positions are NOT documented in our spec; the default
    enables the leading transaction/operlog positions only (attendance + users
    channel, no photos/BIO). Override via `ZKTECO_TRANS_FLAG` with a restart.
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
    ]
    return "\r\n".join(lines) + "\r\n"
