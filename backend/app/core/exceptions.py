"""Application exception hierarchy with stable machine-readable codes."""

from __future__ import annotations


class AppError(Exception):
    code = "INTERNAL_ERROR"
    status_code = 500

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message or self.code)
        if code is not None:
            self.code = code


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = 409


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 422


class AuthError(AppError):
    code = "UNAUTHORIZED"
    status_code = 401


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    status_code = 403


class DeviceNotFoundError(NotFoundError):
    code = "DEVICE_NOT_FOUND"


class DeviceLimitReachedError(AppError):
    code = "DEVICE_LIMIT_REACHED"
    status_code = 503


class CommandQueueFullError(AppError):
    code = "COMMAND_QUEUE_FULL"
    status_code = 409


class DeviceProtocolEvidenceRequiredError(ConflictError):
    """An operation needs a device-specific wire capture before it is safe."""

    code = "DEVICE_PROTOCOL_EVIDENCE_REQUIRED"


class InvalidCommandError(ValidationError):
    code = "INVALID_COMMAND"
