"""Shared constants: statuses, permissions, ADMS whitelists."""

from __future__ import annotations

DEVICE_STATUS_UNKNOWN = "unknown"
DEVICE_STATUS_ONLINE = "online"
DEVICE_STATUS_OFFLINE = "offline"
DEVICE_STATUS_STALE = "stale"
DEVICE_STATUS_DISABLED = "disabled"

DEVICE_STATUSES = frozenset(
    {
        DEVICE_STATUS_UNKNOWN,
        DEVICE_STATUS_ONLINE,
        DEVICE_STATUS_OFFLINE,
        DEVICE_STATUS_STALE,
        DEVICE_STATUS_DISABLED,
    }
)

COMMAND_STATUS_PENDING = "pending"
COMMAND_STATUS_SENT = "sent"
COMMAND_STATUS_CONFIRMED = "confirmed"
COMMAND_STATUS_FAILED = "failed"
COMMAND_STATUS_EXPIRED = "expired"
COMMAND_STATUS_CANCELLED = "cancelled"

COMMAND_STATUSES = frozenset(
    {
        COMMAND_STATUS_PENDING,
        COMMAND_STATUS_SENT,
        COMMAND_STATUS_CONFIRMED,
        COMMAND_STATUS_FAILED,
        COMMAND_STATUS_EXPIRED,
        COMMAND_STATUS_CANCELLED,
    }
)

#: GET OPTION keys confirmed against real devices (see docs/ADMS_PROTOCOL.md §7).
GET_OPTION_KEYS = frozenset(
    {
        "DeviceName",
        "FWVersion",
        "IPAddress",
        "MACAddress",
        "Platform",
        "WorkCode",
        "LockCount",
        "UserCount",
        "FPCount",
        "AttLogCount",
        "FaceCount",
        "TransactionCount",
        "MaxUserCount",
        "MaxAttLogCount",
        "MaxFingerCount",
        "MaxFaceCount",
    }
)

#: Normalized device columns synced from `options` (see ARCHITECTURE §2.2).
#: Aliases cover both wire spellings: registry bodies send `FirmVer`,
#: device-info bodies send `FWVersion`.
OPTION_TO_COLUMN = {
    "DeviceName": "name",
    "FWVersion": "firmware_version",
    "FirmVer": "firmware_version",
    "Platform": "platform",
    "IPAddress": "ip_address",
    "MACAddress": "mac_address",
}

PERMISSIONS = (
    "devices.read",
    "devices.write",
    "devices.delete",
    "attendance.read",
    "attendance.write",
    "attendance.export",
    "device_users.read",
    "device_users.write",
    "device_users.delete",
    "commands.read",
    "commands.execute",
    "users.read",
    "users.write",
    "users.delete",
    "audit.read",
    "companies.read",
    "companies.write",
    "sites.read",
    "sites.write",
    "people.read",
    "people.write",
    "people.sensitive.read",
    "people.sensitive.write",
    "employments.read",
    "employments.write",
    "payroll.read",
    "payroll.write",
    "schedules.read",
    "schedules.write",
    "enrollments.read",
    "enrollments.write",
    "enrollments.approve",
)

DEFAULT_ROLES: dict[str, list[str]] = {
    "admin": list(PERMISSIONS),
    "operator": [
        "devices.read",
        "devices.write",
        "attendance.read",
        "attendance.write",
        "attendance.export",
        "device_users.read",
        "device_users.write",
        "device_users.delete",
        "commands.read",
        "commands.execute",
        "companies.read",
        "sites.read",
        "people.read",
        "employments.read",
        "schedules.read",
        "enrollments.read",
    ],
    "viewer": [
        "devices.read",
        "attendance.read",
        "attendance.export",
        "device_users.read",
        "commands.read",
    ],
}
