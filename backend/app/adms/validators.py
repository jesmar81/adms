"""Serial/body validation — mirrors Laravel `ValidateDeviceRequest` + parser regex."""

from __future__ import annotations

import re

_SERIAL_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_SERIAL_LENGTH = 64


def validate_serial_number(sn: str) -> bool:
    """1-64 chars of [A-Za-z0-9_-]. Rejects SQL/CRLF/control/traversal by charset."""
    if not sn or len(sn) > MAX_SERIAL_LENGTH:
        return False
    return _SERIAL_RE.match(sn) is not None


def check_body_size(body: bytes, limit: int) -> bool:
    return len(body) <= limit
