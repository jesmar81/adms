"""Admin schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 — OAuth2 token type label, not a secret


class DevicePatch(BaseModel):
    """Partial device administration (M-02). `status="active"` clears `disabled`."""

    name: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, pattern="^(disabled|active)$")


class RefreshIn(BaseModel):
    refresh_token: str


class DeviceOut(BaseModel):
    id: uuid.UUID
    serial_number: str
    name: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    platform: str | None = None
    ip_address: str | None = None
    mac_address: str | None = None
    timezone: str
    status: str
    derived_status: str | None = None
    last_activity_at: datetime | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class AttendanceOut(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    device_user_pin: str
    recorded_at: datetime
    status: int
    verify_mode: int
    work_code: str | None = None

    model_config = {"from_attributes": True}


class DeviceUserIn(BaseModel):
    pin: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=255)
    privilege: int = Field(default=0, ge=0, le=14)
    card: str = Field(default="", max_length=128)


class DeviceUserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    privilege: int | None = Field(default=None, ge=0, le=14)
    card: str | None = Field(default=None, max_length=128)
    enabled: bool | None = None


class DeviceUserOut(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    pin: str
    name: str
    privilege: int
    card_number: str | None = None
    enabled: bool
    sync_state: str = "synced"
    last_protocol_command_id: int | None = None

    model_config = {"from_attributes": True}


class CommandIn(BaseModel):
    command_type: str
    params: dict[str, str] = Field(default_factory=dict)


class CommandOut(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    protocol_command_id: int
    command_type: str
    command: str
    status: str
    return_code: int | None = None
    queued_at: datetime
    sent_at: datetime | None = None
    confirmed_at: datetime | None = None

    model_config = {"from_attributes": True}
