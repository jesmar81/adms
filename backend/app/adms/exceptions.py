"""ADMS-specific exceptions (wire-level)."""

from __future__ import annotations

from app.core.exceptions import AppError, ValidationError


class AdmsError(AppError):
    code = "ADMS_ERROR"
    status_code = 400


class InvalidSerialNumberError(ValidationError):
    code = "INVALID_SERIAL"

    def __init__(self, serial: str = "") -> None:
        super().__init__(f"Invalid SN parameter: {serial!r}" if serial else "Invalid SN parameter")


class BodyTooLargeError(AppError):
    code = "BODY_TOO_LARGE"
    status_code = 413

    def __init__(self, limit: int = 0) -> None:
        super().__init__(f"Request body too large (limit {limit} bytes)")
