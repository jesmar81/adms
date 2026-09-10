"""ADMS protocol enums (push-HTTP values; differ from TCP 4370)."""

from __future__ import annotations

from enum import IntEnum


class AttendanceStatus(IntEnum):
    CHECK_IN = 0
    CHECK_OUT = 1
    BREAK_OUT = 2
    BREAK_IN = 3
    OVERTIME_IN = 4
    OVERTIME_OUT = 5

    def label(self) -> str:
        return {
            AttendanceStatus.CHECK_IN: "Check In",
            AttendanceStatus.CHECK_OUT: "Check Out",
            AttendanceStatus.BREAK_OUT: "Break Out",
            AttendanceStatus.BREAK_IN: "Break In",
            AttendanceStatus.OVERTIME_IN: "Overtime In",
            AttendanceStatus.OVERTIME_OUT: "Overtime Out",
        }.get(self, f"Unknown ({int(self)})")


class VerifyMode(IntEnum):
    PASSWORD = 0
    FINGERPRINT = 1
    CARD_LEGACY = 2
    PASSWORD_ALT = 3
    CARD = 4
    FINGERPRINT_CARD = 5
    FINGERPRINT_PASSWORD = 6
    CARD_PASSWORD = 7
    CARD_FINGERPRINT_PASSWORD = 8
    OTHER = 9
    FACE = 15
    PALM = 25

    def label(self) -> str:
        return {
            VerifyMode.PASSWORD: "Password",
            VerifyMode.FINGERPRINT: "Fingerprint",
            VerifyMode.CARD_LEGACY: "Card",
            VerifyMode.PASSWORD_ALT: "Password",
            VerifyMode.CARD: "Card",
            VerifyMode.FINGERPRINT_CARD: "Fingerprint+Card",
            VerifyMode.FINGERPRINT_PASSWORD: "Fingerprint+Password",
            VerifyMode.CARD_PASSWORD: "Card+Password",
            VerifyMode.CARD_FINGERPRINT_PASSWORD: "Card+Fingerprint+Password",
            VerifyMode.OTHER: "Other",
            VerifyMode.FACE: "Face",
            VerifyMode.PALM: "Palm",
        }.get(self, f"Unknown ({int(self)})")


def verify_mode_name(mode: int) -> str:
    try:
        return VerifyMode(mode).label()
    except ValueError:
        return f"Unknown ({mode})"
