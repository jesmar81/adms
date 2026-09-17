"""Whitelisted command construction — the ONLY way to build wire commands.

Never accept free-text `command` from the frontend (§80). Every field is
CRLF-validated to prevent wire-protocol injection (§81). SHELL is disabled (§42).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.constants import GET_OPTION_KEYS
from app.core.exceptions import DeviceProtocolEvidenceRequiredError, InvalidCommandError
from app.models.device import Device


class CommandType(StrEnum):
    INFO = "INFO"
    CHECK = "CHECK"
    LOG = "LOG"
    QUERY_USERINFO = "QUERY_USERINFO"
    UPDATE_USERINFO = "UPDATE_USERINFO"
    DELETE_USERINFO = "DELETE_USERINFO"
    GET_OPTION = "GET_OPTION"


_USER_MUTATION_COMMANDS = frozenset(
    {CommandType.QUERY_USERINFO, CommandType.UPDATE_USERINFO, CommandType.DELETE_USERINFO}
)


def is_security_push_device(device: Device) -> bool:
    """Identify an A&C Security PUSH terminal from persisted registration data."""
    return str((device.options or {}).get("DeviceType", "")).lower() == "acc"


def require_validated_user_command_profile(device: Device, command_type: CommandType) -> None:
    """Block legacy USERINFO wire commands on an unvalidated ACC terminal.

    SpeedFace-V5L A&C PUSH uses a different query/update dialect from legacy
    ADMS. Sending legacy writes can appear successful in our queue while doing
    nothing (or producing an ambiguous negative return) on the terminal.
    """
    if is_security_push_device(device) and command_type in _USER_MUTATION_COMMANDS:
        raise DeviceProtocolEvidenceRequiredError(
            "Security PUSH user synchronization is blocked until a real V5L "
            "querydata/devicecmd capture validates its command format"
        )


def _reject_crlf(field: str, value: str) -> None:
    if "\r" in value or "\n" in value:
        raise InvalidCommandError(f"Command field '{field}' contains forbidden control characters")


@dataclass(frozen=True)
class CommandBuilder:
    """Build validated wire-command strings + their CommandType."""

    @staticmethod
    def info() -> tuple[CommandType, str]:
        return CommandType.INFO, "INFO"

    @staticmethod
    def check() -> tuple[CommandType, str]:
        return CommandType.CHECK, "CHECK"

    @staticmethod
    def log() -> tuple[CommandType, str]:
        return CommandType.LOG, "LOG"

    @staticmethod
    def query_userinfo() -> tuple[CommandType, str]:
        return CommandType.QUERY_USERINFO, "DATA QUERY USERINFO"

    @staticmethod
    def update_userinfo(
        pin: str, name: str, privilege: int = 0, card: str = ""
    ) -> tuple[CommandType, str]:
        """Real devices require `DATA UPDATE USERINFO` (NOT `USER ADD`, §38)."""
        for fname, val in (("pin", pin), ("name", name), ("card", card)):
            _reject_crlf(fname, val)
        if not pin:
            raise InvalidCommandError("pin is required")
        if not 0 <= privilege <= 14:
            raise InvalidCommandError("privilege must be 0-14")
        cmd = f"DATA UPDATE USERINFO PIN={pin}\tName={name}\tPrivilege={privilege}\tCard={card}"
        return CommandType.UPDATE_USERINFO, cmd

    @staticmethod
    def delete_userinfo(pin: str) -> tuple[CommandType, str]:
        """Full word DELETE required — `DATA DEL` fails on devices (§39)."""
        _reject_crlf("pin", pin)
        if not pin:
            raise InvalidCommandError("pin is required")
        return CommandType.DELETE_USERINFO, f"DATA DELETE USERINFO PIN={pin}"

    @staticmethod
    def get_option(key: str) -> tuple[CommandType, str]:
        _reject_crlf("key", key)
        if key not in GET_OPTION_KEYS:
            raise InvalidCommandError(f"Unsupported GET OPTION key: {key!r}")
        return CommandType.GET_OPTION, f"GET OPTION FROM {key}"


def build_command(
    command_type: str, params: dict[str, str] | None = None
) -> tuple[CommandType, str]:
    """Build a command from an API-level type + params dict."""
    params = params or {}
    ctype = CommandType(command_type)
    if ctype is CommandType.INFO:
        return CommandBuilder.info()
    if ctype is CommandType.CHECK:
        return CommandBuilder.check()
    if ctype is CommandType.LOG:
        return CommandBuilder.log()
    if ctype is CommandType.QUERY_USERINFO:
        return CommandBuilder.query_userinfo()
    if ctype is CommandType.UPDATE_USERINFO:
        return CommandBuilder.update_userinfo(
            pin=params.get("pin", ""),
            name=params.get("name", ""),
            privilege=int(params.get("privilege", "0") or 0),
            card=params.get("card", ""),
        )
    if ctype is CommandType.DELETE_USERINFO:
        return CommandBuilder.delete_userinfo(pin=params.get("pin", ""))
    if ctype is CommandType.GET_OPTION:
        return CommandBuilder.get_option(key=params.get("key", ""))
    raise InvalidCommandError(f"Unsupported command type: {command_type}")
