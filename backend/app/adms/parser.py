"""Pure ADMS parsers — no I/O, no DB. Ports Laravel `AttendanceParser`.

Covers: ATTLOG (tab-separated, dual timestamps), KV pairs (device-info +
registry with `~` prefix), USERINFO (tab-separated KV), command results
(batched `&` + shell/multiline `\\n` formats), serial validation.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.adms.validators import validate_serial_number

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_BODY_PREVIEW_LEN = 200


@dataclass(frozen=True)
class AttendanceRecord:
    user_id: str
    timestamp: datetime
    status: int = 0
    verify_mode: int = 0
    work_code: str = ""
    serial_number: str = ""
    # Original wire line (M-05: preserved at parse time, no O(n²) remap later).
    raw_line: str = ""


@dataclass(frozen=True)
class UserRecord:
    pin: str
    name: str = ""
    privilege: int = 0
    card: str = ""
    # Device-side credential, NOT an admin password. Sanitized from logs.
    password: str = ""


@dataclass(frozen=True)
class CommandResult:
    serial_number: str
    protocol_command_id: int
    return_code: int = 0
    command: str = ""

    @property
    def is_success(self) -> bool:
        return self.return_code == 0


@dataclass
class ParseStats:
    total: int = 0
    valid: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def body_preview(body: str | bytes, limit: int = MAX_BODY_PREVIEW_LEN) -> str:
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    return text if len(text) <= limit else text[:limit] + "..."


def _resolve_tz(timezone_name: str) -> timezone | ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def parse_timestamp(value: str, tz: timezone | ZoneInfo) -> datetime | None:
    """Try `Y-m-d H:i:s` (device-local) then Unix epoch. Never invents values."""
    value = value.strip()
    if not value:
        return None
    try:
        naive = datetime.strptime(value, TIMESTAMP_FORMAT)
        return naive.replace(tzinfo=tz)
    except ValueError:
        pass
    stripped = value[1:] if value.startswith(("-", "+")) else value
    if stripped.isdigit():
        try:
            return datetime.fromtimestamp(int(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _parse_int_or_default(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    value = value.strip()
    if not value:
        return default
    # Strict digits (L-04): int("1_0") == 10 in Python but Laravel rejects it.
    if not re.fullmatch(r"[+-]?\d+", value):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def parse_attlog(
    data: str, serial_number: str, timezone_name: str = "UTC"
) -> tuple[list[AttendanceRecord], ParseStats]:
    """Parse ATTLOG body. Malformed lines are skipped, never crash the batch."""
    stats = ParseStats()
    records: list[AttendanceRecord] = []
    tz = _resolve_tz(timezone_name)
    for raw_line in data.strip().strip("\n\r").split("\n"):
        line = raw_line.rstrip("\r")
        if not line.strip():
            continue
        stats.total += 1
        parts = line.split("\t")
        if len(parts) < 2:
            stats.skipped += 1
            stats.errors.append(f"malformed line ({len(parts)} fields)")
            continue
        user_id = parts[0].strip()
        if not user_id:
            stats.skipped += 1
            stats.errors.append("empty UserID")
            continue
        timestamp = parse_timestamp(parts[1], tz)
        if timestamp is None:
            stats.skipped += 1
            stats.errors.append(f"unparseable timestamp: {parts[1]!r}")
            continue
        records.append(
            AttendanceRecord(
                user_id=user_id,
                timestamp=timestamp,
                status=_parse_int_or_default(parts[2] if len(parts) > 2 else None),
                verify_mode=_parse_int_or_default(parts[3] if len(parts) > 3 else None),
                work_code=parts[4].strip() if len(parts) > 4 else "",
                serial_number=serial_number,
                raw_line=line,
            )
        )
        stats.valid += 1
    return records, stats


def parse_rtlog(
    data: str, serial_number: str, timezone_name: str = "UTC"
) -> tuple[list[AttendanceRecord], ParseStats]:
    """Parse Security PUSH ``table=rtlog`` access events as attendance.

    Access-control firmware (``DeviceType=acc``) does not send the legacy
    ``ATTLOG`` tab layout.  It sends tab-separated ``key=value`` fields such
    as ``time``, ``pin``, ``inoutstatus`` and ``verifytype`` instead.  Keep the
    original line so unmapped access-control details remain auditable.
    """
    stats = ParseStats()
    records: list[AttendanceRecord] = []
    tz = _resolve_tz(timezone_name)
    for raw_line in data.strip().strip("\n\r").split("\n"):
        line = raw_line.rstrip("\r")
        if not line.strip():
            continue
        stats.total += 1
        fields: dict[str, str] = {}
        for part in line.split("\t"):
            key, sep, value = part.partition("=")
            if sep:
                fields[key.strip().lower()] = value.strip()
        pin = fields.get("pin", "")
        timestamp_value = fields.get("time", "")
        if not pin:
            stats.skipped += 1
            stats.errors.append("RTLOG line without pin")
            continue
        timestamp = parse_timestamp(timestamp_value, tz)
        if timestamp is None:
            stats.skipped += 1
            stats.errors.append(f"unparseable RTLOG time: {timestamp_value!r}")
            continue
        records.append(
            AttendanceRecord(
                user_id=pin,
                timestamp=timestamp,
                # Security PUSH defines 0 as In and 1 as Out, matching the
                # existing attendance status values.
                status=_parse_int_or_default(fields.get("inoutstatus")),
                verify_mode=_parse_int_or_default(fields.get("verifytype")),
                serial_number=serial_number,
                raw_line=line,
            )
        )
        stats.valid += 1
    return records, stats


def parse_kv_pairs(
    data: str,
    separator: str = "\n",
    key_transform: Callable[[str], None | str] | None = None,
) -> dict[str, str]:
    """General KV parser: device-info (sep `\\n`) and registry (sep `,`)."""
    info: dict[str, str] = {}
    for part in data.strip().split(separator):
        part = part.strip()
        eq = part.find("=")
        if eq == -1:
            continue
        key = part[:eq].strip()
        value = part[eq + 1 :].strip()
        if key_transform is not None:
            transformed = key_transform(key)
            key = transformed if transformed is not None else key
        if key:
            info[key] = value
    return info


def trim_tilde_prefix(key: str) -> str:
    return key.lstrip("~")


def parse_registry_body(data: str) -> dict[str, str]:
    return parse_kv_pairs(data, separator=",", key_transform=trim_tilde_prefix)


def parse_device_info(data: str) -> dict[str, str]:
    info = parse_kv_pairs(data, separator="\n", key_transform=trim_tilde_prefix)
    # A real SpeedFace-V5L INFO response uses ``MAC`` while cdata/registry
    # commonly uses ``MACAddress``. Normalize the transport spelling once.
    if "MAC" in info and "MACAddress" not in info:
        info["MACAddress"] = info["MAC"]
    return info


def parse_info_command_response(data: str) -> dict[str, str]:
    """Extract device inventory from a successful ``devicecmd`` INFO reply."""
    lines = []
    for line in data.replace("\r", "").split("\n"):
        # The first line carries correlation metadata (ID/Return/CMD), not a
        # device option. Remaining lines are the exact INFO inventory.
        if line.strip().upper().startswith(("ID=", "RETURN=", "CMD=")):
            continue
        lines.append(line)
    return parse_device_info("\n".join(lines))


def parse_userinfo(data: str, serial_number: str = "") -> tuple[list[UserRecord], ParseStats]:
    """Parse USERINFO body. Lines without PIN are skipped."""
    _ = serial_number
    stats = ParseStats()
    records: list[UserRecord] = []
    for raw_line in data.strip().split("\n"):
        line = raw_line.rstrip("\r")
        if not line.strip():
            continue
        stats.total += 1
        fields: dict[str, str] = {}
        for part in line.split("\t"):
            eq = part.find("=")
            if eq == -1:
                continue
            fields[part[:eq].strip().lower()] = part[eq + 1 :].strip()
        # Security PUSH querydata commonly spells this ``Pin`` while legacy
        # USERINFO uses ``PIN``.  The fields are otherwise equivalent.
        pin = fields.get("pin", "")
        if not pin:
            stats.skipped += 1
            stats.errors.append("USERINFO line without PIN")
            continue
        records.append(
            UserRecord(
                pin=pin,
                name=fields.get("name", ""),
                privilege=_parse_int_or_default(fields.get("privilege"), 0),
                card=fields.get("card", ""),
                password=fields.get("password", ""),
            )
        )
        stats.valid += 1
    return records, stats


def parse_command_results(body: str, serial_number: str) -> list[CommandResult]:
    """Parse devicecmd body (batched `&` and shell/multiline `\\n` formats).

    Accumulates KV pairs into the current result; each new `ID=` flushes the
    previous one — identical to Laravel's parser.
    """
    results: list[CommandResult] = []
    current_id: int | None = None
    current_return = 0
    current_command = ""
    normalized = body.replace("\n", "&")
    for part in normalized.split("&"):
        part = part.strip()
        if not part:
            continue
        eq = part.find("=")
        if eq == -1:
            continue
        key = part[:eq].strip().upper()
        value = part[eq + 1 :].strip()
        if key == "ID":
            try:
                new_id = int(value)
            except ValueError:
                continue  # unparseable ID: skip, keep accumulating previous
            if current_id is not None:
                results.append(
                    CommandResult(
                        serial_number=serial_number,
                        protocol_command_id=current_id,
                        return_code=current_return,
                        command=current_command,
                    )
                )
            current_id, current_return, current_command = new_id, 0, ""
        elif key == "RETURN":
            try:
                current_return = int(value)
            except ValueError:
                continue
        elif key == "CMD":
            current_command = value
    if current_id is not None:
        results.append(
            CommandResult(
                serial_number=serial_number,
                protocol_command_id=current_id,
                return_code=current_return,
                command=current_command,
            )
        )
    return results


__all__ = [
    "AttendanceRecord",
    "CommandResult",
    "ParseStats",
    "UserRecord",
    "body_preview",
    "parse_attlog",
    "parse_command_results",
    "parse_device_info",
    "parse_info_command_response",
    "parse_kv_pairs",
    "parse_registry_body",
    "parse_rtlog",
    "parse_timestamp",
    "parse_userinfo",
    "trim_tilde_prefix",
    "validate_serial_number",
]
