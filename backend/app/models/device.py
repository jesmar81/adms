"""Device aggregate: devices, users on device, attendance, payloads, commands, events (§12-22)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB as _PGJSONB  # noqa: F401  (documents PG type)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.types import GUID, INET, JSONBVariant


class Device(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "devices"

    serial_number: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manufacturer: Mapped[str] = mapped_column(String(100), default="ZKTeco", nullable=False)
    firmware_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    push_protocol: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET(), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_registry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_cdata_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_command_poll_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_command_result_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Security PUSH (DeviceType=acc) registration/session identifiers.  They
    # are protocol state, not credentials exposed through the admin API.
    adms_registry_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    adms_session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)

    # Monotonic per-device wire-command counter (M-08: allocated under row lock).
    command_seq: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    options: Mapped[dict[str, Any]] = mapped_column(JSONBVariant, default=dict, nullable=False)
    last_registry_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBVariant, nullable=True
    )
    last_device_info: Mapped[dict[str, Any] | None] = mapped_column(JSONBVariant, nullable=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONBVariant, default=dict, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("serial_number", name="uq_devices_serial_number"),
        CheckConstraint(
            "status IN ('unknown','online','offline','stale','disabled')", name="ck_devices_status"
        ),
        Index("ix_devices_status", "status"),
        Index("ix_devices_last_activity", "last_activity_at"),
    )


class DeviceUser(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "device_users"

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    pin: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    privilege: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    card_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Device-side credential (§15). NULL unless ZKTECO_PERSIST_DEVICE_PASSWORD.
    device_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONBVariant, default=dict, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Desired-vs-confirmed lifecycle (M-03): API writes intent (pending),
    # devicecmd confirmations reconcile to synced/failed (or delete the row).
    sync_state: Mapped[str] = mapped_column(String(20), default="synced", nullable=False)
    pending_op: Mapped[dict[str, Any] | None] = mapped_column(JSONBVariant, nullable=True)
    last_protocol_command_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint("device_id", "pin", name="uq_device_users_device_pin"),
        CheckConstraint(
            "sync_state IN ('synced','pending','failed')", name="ck_device_users_sync_state"
        ),
        Index("ix_device_users_device", "device_id"),
        Index("ix_device_users_person", "person_id"),
    )


class AttendanceLog(Base, UUIDPKMixin):
    __tablename__ = "attendance_logs"

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    device_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("device_users.id", ondelete="SET NULL"), nullable=True
    )
    device_user_pin: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    device_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    verify_mode: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    work_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("adms_payloads.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(30), default="adms", nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "device_user_pin",
            "recorded_at",
            "status",
            "verify_mode",
            "work_code",
            name="uq_attendance_dedup",
        ),
        Index("ix_attendance_device", "device_id"),
        Index("ix_attendance_pin", "device_user_pin"),
        Index("ix_attendance_recorded", "recorded_at"),
        Index("ix_attendance_device_recorded", "device_id", "recorded_at"),
    )


class AdmsPayload(Base, UUIDPKMixin):
    __tablename__ = "adms_payloads"

    device_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    endpoint: Mapped[str] = mapped_column(String(50), nullable=False)
    data_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    headers: Mapped[dict[str, Any] | None] = mapped_column(JSONBVariant, nullable=True)
    query_params: Mapped[dict[str, Any] | None] = mapped_column(JSONBVariant, nullable=True)
    raw_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(30), default="received", nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_payloads_device_received", "device_id", "received_at"),)


class DeviceCommand(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "device_commands"

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    protocol_command_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    command_type: Mapped[str] = mapped_column(String(50), nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONBVariant, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    return_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("device_id", "protocol_command_id", name="uq_cmd_device_proto"),
        CheckConstraint(
            "status IN ('pending','sent','confirmed','failed','expired','cancelled')",
            name="ck_cmd_status",
        ),
        Index("ix_cmd_device", "device_id"),
        Index("ix_cmd_status", "status"),
    )


class DeviceEvent(Base):
    __tablename__ = "device_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONBVariant, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_events_device", "device_id"),
        Index("ix_events_type", "event_type"),
        Index("ix_events_created", "created_at"),
    )
