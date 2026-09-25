"""Corporate group, people and employment aggregates.

Biometric templates and personal tax/social-security identifiers intentionally
do not live here.  They require a dedicated encrypted store and retention
controls; these tables establish the auditable business context first.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    address: Mapped[Address | None] = relationship(
        back_populates="company",
        foreign_keys="Address.company_id",
        uselist=False,
        cascade="all, delete-orphan",
    )

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
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    address: Mapped[Address | None] = relationship(
        back_populates="site",
        foreign_keys="Address.site_id",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_sites_company_code"),
        Index("ix_sites_company", "company_id"),
    )


class Address(Base, UUIDPKMixin, TimestampMixin):
    """Structured Mexican business address owned by one company or one branch."""

    __tablename__ = "addresses"

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("sites.id", ondelete="CASCADE"), nullable=True
    )
    street: Mapped[str | None] = mapped_column(String(150), nullable=True)
    exterior_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    interior_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    neighborhood: Mapped[str | None] = mapped_column(String(100), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    country: Mapped[str] = mapped_column(String(80), default="México", nullable=False)
    reference_notes: Mapped[str | None] = mapped_column(String(250), nullable=True)

    company: Mapped[Company | None] = relationship(
        back_populates="address", foreign_keys=[company_id]
    )
    site: Mapped[Site | None] = relationship(back_populates="address", foreign_keys=[site_id])

    __table_args__ = (
        CheckConstraint(
            "(company_id IS NOT NULL AND site_id IS NULL) OR "
            "(company_id IS NULL AND site_id IS NOT NULL)",
            name="ck_addresses_exactly_one_owner",
        ),
        UniqueConstraint("company_id", name="uq_addresses_company"),
        UniqueConstraint("site_id", name="uq_addresses_site"),
        Index("ix_addresses_company", "company_id"),
        Index("ix_addresses_site", "site_id"),
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
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(32), nullable=True)
    marital_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(80), nullable=True)
    birth_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_street: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address_ext_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_int_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_neighborhood: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_municipality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    emergency_contact_relationship: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (Index("ix_people_group", "corporate_group_id"),)


class PersonSensitiveIdentifier(Base, UUIDPKMixin, TimestampMixin):
    """Encrypted Mexican tax and social-security identifiers for one person.

    The application key is deployment-owned.  Plaintext values are never
    persisted or included in audit metadata.
    """

    __tablename__ = "person_sensitive_identifiers"

    person_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    curp_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    rfc_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    nss_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    fiscal_name_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_regime_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    fiscal_postal_code_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    curp_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rfc_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nss_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("person_id", name="uq_person_sensitive_identifiers_person"),
        Index("ix_person_sensitive_identifiers_curp_hash", "curp_hash"),
        Index("ix_person_sensitive_identifiers_rfc_hash", "rfc_hash"),
        Index("ix_person_sensitive_identifiers_nss_hash", "nss_hash"),
    )


class PersonPhoto(Base, UUIDPKMixin, TimestampMixin):
    """One consented profile photograph, stored with the worker record.

    This is an HR profile image, never a device biometric template or face
    recognition payload. Access is protected by the people permission scope.
    """

    __tablename__ = "person_photos"

    person_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    image_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (UniqueConstraint("person_id", name="uq_person_photos_person"),)


class Employment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "employments"

    person_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("people.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )
    employee_number: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[str | None] = mapped_column(String(150), nullable=True)
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cost_center: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manager_person_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    contract_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    employment_relation_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    job_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    probation_ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "employee_number", name="uq_employments_company_number"),
        Index("ix_employments_person", "person_id"),
        Index("ix_employments_company", "company_id"),
        Index("ix_employments_site", "site_id"),
    )


class EmploymentCompensation(Base, UUIDPKMixin, TimestampMixin):
    """Payroll and IMSS fields, restricted to the payroll permission scope."""

    __tablename__ = "employment_compensations"

    employment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("employments.id", ondelete="CASCADE"), nullable=False
    )
    daily_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    integrated_daily_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    pay_frequency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bank_clabe_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    imss_umf: Mapped[str | None] = mapped_column(String(16), nullable=True)
    imss_worker_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    imss_salary_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    imss_workday_type: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        UniqueConstraint("employment_id", name="uq_employment_compensations_employment"),
    )


class WorkSchedule(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "work_schedules"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    automatic_exit_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "company_id", "name", "version", name="uq_work_schedules_company_name_version"
        ),
        Index("ix_work_schedules_company", "company_id"),
    )


class Holiday(Base, UUIDPKMixin, TimestampMixin):
    """Company calendar day, generated from law or explicitly declared by HR."""

    __tablename__ = "holidays"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_paid_rest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint("kind IN ('statutory','company','electoral')", name="ck_holidays_kind"),
        UniqueConstraint("company_id", "holiday_date", name="uq_holidays_company_date"),
        Index("ix_holidays_company_date", "company_id", "holiday_date"),
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
        Index(
            "uq_schedule_assignments_one_current_employment",
            "employment_id",
            unique=True,
            postgresql_where=active.is_(True) & effective_to.is_(None),
        ),
    )


class AttendanceAdjustment(Base, UUIDPKMixin, TimestampMixin):
    """HR override for one worker-day; raw clock events remain immutable.

    An override is deliberately stored at the daily-card layer.  It can fill
    any missing event, replace an event wrongly attributed by the terminal,
    or classify a no-show.  The audit log records every change made to it.
    """

    __tablename__ = "attendance_adjustments"

    employment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("employments.id", ondelete="RESTRICT"), nullable=False
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meal_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meal_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    absence_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "absence_kind IS NULL OR absence_kind IN ('justified', 'unjustified')",
            name="ck_attendance_adjustments_absence_kind",
        ),
        UniqueConstraint("employment_id", "attendance_date", name="uq_attendance_adjustments_day"),
        Index("ix_attendance_adjustments_employment_day", "employment_id", "attendance_date"),
    )


class OvertimeRequest(Base, UUIDPKMixin, TimestampMixin):
    """A governed overtime candidate; raw terminal evidence remains immutable."""

    __tablename__ = "overtime_requests"

    employment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("employments.id", ondelete="RESTRICT"), nullable=False
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending_hr", nullable=False)
    scheduled_exit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    detected_exit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    authorized_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authorized_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authorization_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        CheckConstraint("source IN ('detected', 'manual')", name="ck_overtime_requests_source"),
        CheckConstraint(
            "status IN ('pending_hr', 'pending_direction', 'approved', 'rejected', 'cancelled')",
            name="ck_overtime_requests_status",
        ),
        CheckConstraint("minutes BETWEEN 1 AND 720", name="ck_overtime_requests_minutes"),
        CheckConstraint(
            "reviewed_minutes IS NULL OR reviewed_minutes BETWEEN 1 AND 720",
            name="ck_overtime_requests_reviewed_minutes",
        ),
        CheckConstraint(
            "authorized_minutes IS NULL OR authorized_minutes BETWEEN 1 AND 720",
            name="ck_overtime_requests_authorized_minutes",
        ),
        UniqueConstraint("employment_id", "attendance_date", name="uq_overtime_requests_day"),
        Index("ix_overtime_requests_employment_day", "employment_id", "attendance_date"),
        Index("ix_overtime_requests_status", "status"),
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
    identity_verified_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    identity_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    identity_verification_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('requested','identity_verified','approved','awaiting_device_enrollment',"
            "'verification_pending','completed','rejected','revoked')",
            name="ck_enrollment_requests_status",
        ),
        Index("ix_enrollment_requests_employment", "employment_id"),
        Index("ix_enrollment_requests_device", "device_id"),
    )
