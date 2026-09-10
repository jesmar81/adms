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
