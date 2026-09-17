"""Corporate group, people and employment aggregates.

Biometric templates and personal tax/social-security identifiers intentionally
do not live here.  They require a dedicated encrypted store and retention
controls; these tables establish the auditable business context first.
"""

from __future__ import annotations

import uuid
from datetime import date, time
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.types import GUID, JSONBVariant


class CorporateGroup(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "corporate_groups"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("code", name="uq_corporate_groups_code"),)


class Company(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "companies"

    corporate_group_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("corporate_groups.id", ondelete="RESTRICT"), nullable=False
    )
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(13), nullable=True)
    employer_registration: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Mexico_City", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("corporate_group_id", "legal_name", name="uq_companies_group_legal_name"),
        Index("ix_companies_group", "corporate_group_id"),
    )


class Site(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "sites"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Mexico_City", nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_sites_company_code"),
        Index("ix_sites_company", "company_id"),
    )


class Person(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "people"

    corporate_group_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("corporate_groups.id", ondelete="RESTRICT"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    second_last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (Index("ix_people_group", "corporate_group_id"),)


class Employment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "employments"

    person_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("people.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    employee_number: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[str | None] = mapped_column(String(150), nullable=True)
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cost_center: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manager_person_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    contract_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "employee_number", name="uq_employments_company_number"),
        Index("ix_employments_person", "person_id"),
        Index("ix_employments_company", "company_id"),
    )


class WorkSchedule(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "work_schedules"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "company_id", "name", "version", name="uq_work_schedules_company_name_version"
        ),
        Index("ix_work_schedules_company", "company_id"),
    )


class ScheduleSlot(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "schedule_slots"

    work_schedule_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("work_schedules.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    expected_at: Mapped[time] = mapped_column(Time, nullable=False)
    window_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    window_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    tolerance_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_schedule_slots_day_of_week"),
        CheckConstraint(
            "kind IN ('entry','meal_out','meal_in','exit')", name="ck_schedule_slots_kind"
        ),
        CheckConstraint("tolerance_minutes >= 0", name="ck_schedule_slots_tolerance"),
        UniqueConstraint(
            "work_schedule_id", "day_of_week", "kind", "sequence", name="uq_schedule_slots_position"
        ),
        Index("ix_schedule_slots_schedule", "work_schedule_id"),
    )


class ScheduleAssignment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "schedule_assignments"

    employment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("employments.id", ondelete="RESTRICT"), nullable=False
    )
    work_schedule_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("work_schedules.id", ondelete="RESTRICT"), nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_schedule_assignments_date_range",
        ),
        Index("ix_schedule_assignments_employment", "employment_id"),
    )


class EnrollmentRequest(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "enrollment_requests"

    employment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("employments.id", ondelete="RESTRICT"), nullable=False
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False
    )
    methods: Mapped[dict[str, Any]] = mapped_column(JSONBVariant, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="requested", nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('requested','approved','awaiting_device_enrollment',"
            "'verification_pending','completed','rejected','revoked')",
            name="ck_enrollment_requests_status",
        ),
        Index("ix_enrollment_requests_employment", "employment_id"),
        Index("ix_enrollment_requests_device", "device_id"),
    )
