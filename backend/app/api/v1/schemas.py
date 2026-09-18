"""Admin schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Nationality = Literal["Mexicana", "Extranjera"]
MaritalStatus = Literal[
    "Soltero(a)",
    "Casado(a)",
    "Unión libre",
    "Divorciado(a)",
    "Viudo(a)",
    "Separado(a)",
]
EmergencyRelationship = Literal[
    "Madre",
    "Padre",
    "Cónyuge",
    "Pareja",
    "Hijo(a)",
    "Hermano(a)",
    "Tutor(a)",
    "Otro",
]

MEXICAN_STATES = frozenset(
    (
        "Aguascalientes",
        "Baja California",
        "Baja California Sur",
        "Campeche",
        "Chiapas",
        "Chihuahua",
        "Ciudad de México",
        "Coahuila de Zaragoza",
        "Colima",
        "Durango",
        "Estado de México",
        "Guanajuato",
        "Guerrero",
        "Hidalgo",
        "Jalisco",
        "Michoacán de Ocampo",
        "Morelos",
        "Nayarit",
        "Nuevo León",
        "Oaxaca",
        "Puebla",
        "Querétaro",
        "Quintana Roo",
        "San Luis Potosí",
        "Sinaloa",
        "Sonora",
        "Tabasco",
        "Tamaulipas",
        "Tlaxcala",
        "Veracruz de Ignacio de la Llave",
        "Yucatán",
        "Zacatecas",
    )
)


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
    site_id: uuid.UUID | None = None
    status: str | None = Field(default=None, pattern="^(disabled|active)$")


class CorporateGroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")


class CorporateGroupOut(CorporateGroupIn):
    id: uuid.UUID
    active: bool

    model_config = {"from_attributes": True}


class BusinessAddress(BaseModel):
    """One Mexican address, reusable by a company or a branch."""

    street: str | None = Field(default=None, max_length=150)
    exterior_number: str | None = Field(default=None, max_length=20)
    interior_number: str | None = Field(default=None, max_length=20)
    neighborhood: str | None = Field(default=None, max_length=100)
    municipality: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, min_length=5, max_length=5, pattern=r"^\d{5}$")
    country: str = Field(default="México", max_length=80)
    reference_notes: str | None = Field(default=None, max_length=250)

    model_config = {"from_attributes": True}

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str | None) -> str | None:
        if value is not None and value not in MEXICAN_STATES:
            raise ValueError("must be one of Mexico's 32 federal entities")
        return value


class BusinessAddressOut(BusinessAddress):
    id: uuid.UUID

    model_config = {"from_attributes": True}


class CompanyIn(BaseModel):
    corporate_group_id: uuid.UUID
    legal_name: str = Field(min_length=1, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=13)
    employer_registration: str | None = Field(default=None, max_length=32)
    timezone: str = Field(default="America/Mexico_City", max_length=64)
    address: BusinessAddress | None = None


class CompanyOut(CompanyIn):
    id: uuid.UUID
    address: BusinessAddressOut | None = None
    active: bool

    model_config = {"from_attributes": True}


class CompanyPatch(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=13)
    employer_registration: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    address: BusinessAddress | None = None
    active: bool | None = None


class SiteIn(BaseModel):
    company_id: uuid.UUID
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=50)
    timezone: str = Field(default="America/Mexico_City", max_length=64)
    address: BusinessAddress | None = None


class SiteOut(SiteIn):
    id: uuid.UUID
    address: BusinessAddressOut | None = None
    active: bool

    model_config = {"from_attributes": True}


class SitePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    timezone: str | None = Field(default=None, max_length=64)
    address: BusinessAddress | None = None
    active: bool | None = None


class HardDeleteCaptchaOut(BaseModel):
    token: str
    prompt: str
    expires_in_seconds: int


class HardDeleteIn(BaseModel):
    captcha_token: str = Field(min_length=16, max_length=128)
    captcha_answer: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PersonProfileCatalog(BaseModel):
    """Server-side catalog rules for the common Mexican employee profile."""

    @field_validator("birth_state", "address_state", check_fields=False)
    @classmethod
    def validate_mexican_state(cls, value: str | None) -> str | None:
        if value is not None and value not in MEXICAN_STATES:
            raise ValueError("must be one of Mexico's 32 federal entities")
        return value


class PersonIn(PersonProfileCatalog):
    corporate_group_id: uuid.UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    second_last_name: str | None = Field(default=None, max_length=100)
    preferred_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    birth_date: date | None = None
    sex: str | None = Field(default=None, max_length=32)
    marital_status: MaritalStatus | None = None
    nationality: Nationality | None = "Mexicana"
    birth_state: str | None = Field(default=None, max_length=100)
    address_street: str | None = Field(default=None, max_length=150)
    address_ext_number: str | None = Field(default=None, max_length=20)
    address_int_number: str | None = Field(default=None, max_length=20)
    address_neighborhood: str | None = Field(default=None, max_length=100)
    address_municipality: str | None = Field(default=None, max_length=100)
    address_state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=10)
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = Field(default=None, max_length=32)
    emergency_contact_relationship: EmergencyRelationship | None = None


class PersonOut(PersonIn):
    id: uuid.UUID
    active: bool

    model_config = {"from_attributes": True}


class PersonPatch(PersonProfileCatalog):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    second_last_name: str | None = Field(default=None, max_length=100)
    preferred_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    birth_date: date | None = None
    sex: str | None = Field(default=None, max_length=32)
    marital_status: MaritalStatus | None = None
    nationality: Nationality | None = None
    birth_state: str | None = Field(default=None, max_length=100)
    address_street: str | None = Field(default=None, max_length=150)
    address_ext_number: str | None = Field(default=None, max_length=20)
    address_int_number: str | None = Field(default=None, max_length=20)
    address_neighborhood: str | None = Field(default=None, max_length=100)
    address_municipality: str | None = Field(default=None, max_length=100)
    address_state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=10)
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = Field(default=None, max_length=32)
    emergency_contact_relationship: EmergencyRelationship | None = None
    active: bool | None = None


class PersonSensitiveIdentifiersIn(BaseModel):
    curp: str | None = Field(default=None, min_length=18, max_length=18)
    rfc: str | None = Field(default=None, min_length=12, max_length=13)
    nss: str | None = Field(default=None, min_length=11, max_length=11)
    fiscal_name: str | None = Field(default=None, max_length=255)
    tax_regime: str | None = Field(default=None, max_length=16)
    fiscal_postal_code: str | None = Field(default=None, min_length=5, max_length=5)


class PersonSensitiveIdentifiersOut(BaseModel):
    curp: str | None = None
    rfc: str | None = None
    nss: str | None = None
    fiscal_name: str | None = None
    tax_regime: str | None = None
    fiscal_postal_code: str | None = None


class PersonPhotoOut(BaseModel):
    content_type: str
    size_bytes: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmploymentIn(BaseModel):
    company_id: uuid.UUID
    site_id: uuid.UUID | None = None
    employee_number: str = Field(min_length=1, max_length=64)
    position: str | None = Field(default=None, max_length=150)
    department: str | None = Field(default=None, max_length=150)
    cost_center: str | None = Field(default=None, max_length=100)
    manager_person_id: uuid.UUID | None = None
    contract_type: str | None = Field(default=None, max_length=80)
    employment_relation_type: str | None = Field(default=None, max_length=80)
    job_category: str | None = Field(default=None, max_length=100)
    work_location: str | None = Field(default=None, max_length=150)
    started_on: date
    ended_on: date | None = None
    probation_ends_on: date | None = None


class EmploymentOut(EmploymentIn):
    id: uuid.UUID
    person_id: uuid.UUID
    active: bool

    model_config = {"from_attributes": True}


class EmploymentCompensationIn(BaseModel):
    daily_salary: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    integrated_daily_salary: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    pay_frequency: str | None = Field(default=None, max_length=32)
    payment_method: str | None = Field(default=None, max_length=32)
    bank_clabe: str | None = Field(default=None, min_length=18, max_length=18)
    imss_umf: str | None = Field(default=None, max_length=16)
    imss_worker_type: str | None = Field(default=None, max_length=16)
    imss_salary_type: str | None = Field(default=None, max_length=16)
    imss_workday_type: str | None = Field(default=None, max_length=16)


class EmploymentCompensationOut(EmploymentCompensationIn):
    employment_id: uuid.UUID


class ScheduleSlotIn(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    kind: str = Field(pattern="^(entry|meal_out|meal_in|exit)$")
    sequence: int = Field(default=1, ge=1, le=20)
    expected_at: time
    window_start: time | None = None
    window_end: time | None = None
    tolerance_minutes: int = Field(default=0, ge=0, le=1440)
    required: bool = True


class WorkScheduleIn(BaseModel):
    company_id: uuid.UUID
    name: str = Field(min_length=1, max_length=150)
    timezone: str = Field(default="America/Mexico_City", max_length=64)
    slots: list[ScheduleSlotIn] = Field(default_factory=list, max_length=100)


class WorkSchedulePatch(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    timezone: str = Field(default="America/Mexico_City", max_length=64)
    slots: list[ScheduleSlotIn] = Field(min_length=1, max_length=100)


class ScheduleSlotOut(ScheduleSlotIn):
    id: uuid.UUID
    work_schedule_id: uuid.UUID

    model_config = {"from_attributes": True}


class WorkScheduleOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    timezone: str
    version: int
    active: bool
    slots: list[ScheduleSlotOut] = Field(default_factory=list)


class HolidayIn(BaseModel):
    company_id: uuid.UUID
    holiday_date: date
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(default="company", pattern="^(company|electoral)$")
    is_paid_rest: bool = True


class HolidayOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    holiday_date: date
    name: str
    kind: str
    source: str | None
    is_paid_rest: bool
    generated: bool

    model_config = {"from_attributes": True}


class HolidayGenerationOut(BaseModel):
    year: int
    created: int
    existing: int


class ScheduleAssignmentIn(BaseModel):
    work_schedule_id: uuid.UUID
    effective_from: date
    effective_to: date | None = None


class ScheduleAssignmentOut(ScheduleAssignmentIn):
    id: uuid.UUID
    employment_id: uuid.UUID
    active: bool

    model_config = {"from_attributes": True}


class EnrollmentRequestIn(BaseModel):
    employment_id: uuid.UUID
    device_id: uuid.UUID
    methods: list[str] = Field(min_length=1, max_length=4)
    note: str | None = Field(default=None, max_length=2000)


class EnrollmentRequestStatusIn(BaseModel):
    status: str = Field(
        pattern="^(approved|awaiting_device_enrollment|verification_pending|completed|rejected|revoked)$"
    )
    note: str | None = Field(default=None, max_length=2000)


class EnrollmentRequestOut(BaseModel):
    id: uuid.UUID
    employment_id: uuid.UUID
    device_id: uuid.UUID
    methods: list[str]
    status: str
    requested_by: uuid.UUID | None = None
    approved_by: uuid.UUID | None = None
    completed_by: uuid.UUID | None = None
    note: str | None = None

    model_config = {"from_attributes": True}


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
    site_id: uuid.UUID | None = None
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


class PersonAttendancePageOut(BaseModel):
    """A stable keyset page of raw attendance marks for one person."""

    items: list[AttendanceOut]
    next_cursor: str | None = None


class DeviceUserIn(BaseModel):
    person_id: uuid.UUID | None = None
    pin: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=255)
    privilege: int = Field(default=0, ge=0, le=14)
    card: str = Field(default="", max_length=128)


class DeviceUserUpdate(BaseModel):
    person_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=255)
    privilege: int | None = Field(default=None, ge=0, le=14)
    card: str | None = Field(default=None, max_length=128)
    enabled: bool | None = None


class DeviceUserOut(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    person_id: uuid.UUID | None = None
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
