"""Corporate, people and employment administration endpoints."""

from __future__ import annotations

import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import deps
from app.api.v1.schemas import (
    CompanyIn,
    CompanyOut,
    CorporateGroupIn,
    CorporateGroupOut,
    EmploymentIn,
    EmploymentOut,
    EnrollmentRequestIn,
    EnrollmentRequestOut,
    EnrollmentRequestStatusIn,
    PersonIn,
    PersonOut,
    ScheduleAssignmentIn,
    ScheduleAssignmentOut,
    ScheduleSlotOut,
    SiteIn,
    SiteOut,
    WorkScheduleIn,
    WorkScheduleOut,
)
from app.core.database import get_db
from app.models.device import Device
from app.models.hr import (
    Company,
    CorporateGroup,
    Employment,
    EnrollmentRequest,
    Person,
    ScheduleAssignment,
    ScheduleSlot,
    Site,
    WorkSchedule,
)
from app.models.user import User
from app.services import audit as audit_svc


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid timezone: {value}") from exc


async def _audit(
    session: AsyncSession,
    user: User,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    rid: str,
) -> None:
    await audit_svc.record(
        session,
        action=action,
        user_id=user.id,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=rid,
    )


groups_router = APIRouter(prefix="/corporate-groups", tags=["corporate-groups"])


@groups_router.get("", response_model=list[CorporateGroupOut])
async def list_groups(
    _user: User = Depends(deps.require_permission("companies.read")),
    session: AsyncSession = Depends(get_db),
) -> list[CorporateGroup]:
    result = await session.execute(select(CorporateGroup).order_by(CorporateGroup.name))
    return list(result.scalars())


@groups_router.post("", response_model=CorporateGroupOut, status_code=201)
async def create_group(
    payload: CorporateGroupIn,
    user: User = Depends(deps.require_permission("companies.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> CorporateGroup:
    if await session.scalar(select(CorporateGroup).where(CorporateGroup.code == payload.code)):
        raise HTTPException(status_code=409, detail="Corporate group code already exists")
    row = CorporateGroup(**payload.model_dump())
    session.add(row)
    await session.flush()
    await _audit(session, user, "corporate_group.create", "corporate_group", row.id, rid)
    await session.commit()
    return row


companies_router = APIRouter(prefix="/companies", tags=["companies"])


@companies_router.get("", response_model=list[CompanyOut])
async def list_companies(
    corporate_group_id: uuid.UUID | None = None,
    _user: User = Depends(deps.require_permission("companies.read")),
    session: AsyncSession = Depends(get_db),
) -> list[Company]:
    query = select(Company).order_by(Company.legal_name)
    if corporate_group_id:
        query = query.where(Company.corporate_group_id == corporate_group_id)
    return list((await session.execute(query)).scalars())


@companies_router.post("", response_model=CompanyOut, status_code=201)
async def create_company(
    payload: CompanyIn,
    user: User = Depends(deps.require_permission("companies.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Company:
    _validate_timezone(payload.timezone)
    if await session.get(CorporateGroup, payload.corporate_group_id) is None:
        raise HTTPException(status_code=404, detail="Corporate group not found")
    row = Company(**payload.model_dump())
    session.add(row)
    await session.flush()
    await _audit(session, user, "company.create", "company", row.id, rid)
    await session.commit()
    return row


sites_router = APIRouter(prefix="/sites", tags=["sites"])


@sites_router.get("", response_model=list[SiteOut])
async def list_sites(
    company_id: uuid.UUID | None = None,
    _user: User = Depends(deps.require_permission("sites.read")),
    session: AsyncSession = Depends(get_db),
) -> list[Site]:
    query = select(Site).order_by(Site.name)
    if company_id:
        query = query.where(Site.company_id == company_id)
    return list((await session.execute(query)).scalars())


@sites_router.post("", response_model=SiteOut, status_code=201)
async def create_site(
    payload: SiteIn,
    user: User = Depends(deps.require_permission("sites.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Site:
    _validate_timezone(payload.timezone)
    if await session.get(Company, payload.company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    row = Site(**payload.model_dump())
    session.add(row)
    await session.flush()
    await _audit(session, user, "site.create", "site", row.id, rid)
    await session.commit()
    return row


people_router = APIRouter(prefix="/people", tags=["people"])


@people_router.get("", response_model=list[PersonOut])
async def list_people(
    corporate_group_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    _user: User = Depends(deps.require_permission("people.read")),
    session: AsyncSession = Depends(get_db),
) -> list[Person]:
    query = (
        select(Person)
        .where(Person.corporate_group_id == corporate_group_id)
        .order_by(Person.last_name, Person.first_name)
        .limit(limit)
    )
    return list((await session.execute(query)).scalars())


@people_router.post("", response_model=PersonOut, status_code=201)
async def create_person(
    payload: PersonIn,
    user: User = Depends(deps.require_permission("people.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Person:
    if await session.get(CorporateGroup, payload.corporate_group_id) is None:
        raise HTTPException(status_code=404, detail="Corporate group not found")
    row = Person(**payload.model_dump())
    session.add(row)
    await session.flush()
    await _audit(session, user, "person.create", "person", row.id, rid)
    await session.commit()
    return row


employments_router = APIRouter(prefix="/employments", tags=["employments"])


@employments_router.get("", response_model=list[EmploymentOut])
async def list_employments(
    company_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    _user: User = Depends(deps.require_permission("employments.read")),
    session: AsyncSession = Depends(get_db),
) -> list[Employment]:
    query = select(Employment).order_by(Employment.employee_number)
    if company_id:
        query = query.where(Employment.company_id == company_id)
    if person_id:
        query = query.where(Employment.person_id == person_id)
    return list((await session.execute(query)).scalars())


@people_router.post("/{person_id}/employments", response_model=EmploymentOut, status_code=201)
async def create_employment(
    person_id: uuid.UUID,
    payload: EmploymentIn,
    user: User = Depends(deps.require_permission("employments.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Employment:
    person = await session.get(Person, person_id)
    company = await session.get(Company, payload.company_id)
    if person is None or company is None:
        raise HTTPException(status_code=404, detail="Person or company not found")
    if person.corporate_group_id != company.corporate_group_id:
        raise HTTPException(status_code=422, detail="Person and company belong to different groups")
    if payload.ended_on is not None and payload.ended_on < payload.started_on:
        raise HTTPException(status_code=422, detail="ended_on must not precede started_on")
    row = Employment(person_id=person_id, **payload.model_dump())
    session.add(row)
    await session.flush()
    await _audit(session, user, "employment.create", "employment", row.id, rid)
    await session.commit()
    return row


schedules_router = APIRouter(prefix="/work-schedules", tags=["work-schedules"])


def _schedule_out(row: WorkSchedule, slots: list[ScheduleSlot]) -> WorkScheduleOut:
    return WorkScheduleOut(
        id=row.id,
        company_id=row.company_id,
        name=row.name,
        timezone=row.timezone,
        version=row.version,
        active=row.active,
        slots=[ScheduleSlotOut.model_validate(slot) for slot in slots],
    )


@schedules_router.get("", response_model=list[WorkScheduleOut])
async def list_work_schedules(
    company_id: uuid.UUID | None = None,
    _user: User = Depends(deps.require_permission("schedules.read")),
    session: AsyncSession = Depends(get_db),
) -> list[WorkScheduleOut]:
    query = select(WorkSchedule).order_by(WorkSchedule.name, WorkSchedule.version)
    if company_id:
        query = query.where(WorkSchedule.company_id == company_id)
    schedules = list((await session.execute(query)).scalars())
    if not schedules:
        return []
    ids = [row.id for row in schedules]
    slots = list(
        (
            await session.execute(
                select(ScheduleSlot)
                .where(ScheduleSlot.work_schedule_id.in_(ids))
                .order_by(ScheduleSlot.day_of_week, ScheduleSlot.expected_at, ScheduleSlot.sequence)
            )
        ).scalars()
    )
    slots_by_schedule: dict[uuid.UUID, list[ScheduleSlot]] = {key: [] for key in ids}
    for slot in slots:
        slots_by_schedule[slot.work_schedule_id].append(slot)
    return [_schedule_out(row, slots_by_schedule[row.id]) for row in schedules]


@schedules_router.post("", response_model=WorkScheduleOut, status_code=201)
async def create_work_schedule(
    payload: WorkScheduleIn,
    user: User = Depends(deps.require_permission("schedules.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> WorkScheduleOut:
    _validate_timezone(payload.timezone)
    if await session.get(Company, payload.company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    positions = {(slot.day_of_week, slot.kind, slot.sequence) for slot in payload.slots}
    if len(positions) != len(payload.slots):
        raise HTTPException(status_code=422, detail="Duplicate schedule slot position")
    row = WorkSchedule(
        company_id=payload.company_id,
        name=payload.name,
        timezone=payload.timezone,
    )
    session.add(row)
    await session.flush()
    slots = [ScheduleSlot(work_schedule_id=row.id, **slot.model_dump()) for slot in payload.slots]
    session.add_all(slots)
    await session.flush()
    await _audit(session, user, "work_schedule.create", "work_schedule", row.id, rid)
    await session.commit()
    return _schedule_out(row, slots)


@employments_router.post(
    "/{employment_id}/schedule-assignments", response_model=ScheduleAssignmentOut, status_code=201
)
async def assign_schedule(
    employment_id: uuid.UUID,
    payload: ScheduleAssignmentIn,
    user: User = Depends(deps.require_permission("schedules.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> ScheduleAssignment:
    employment = await session.get(Employment, employment_id)
    schedule = await session.get(WorkSchedule, payload.work_schedule_id)
    if employment is None or schedule is None:
        raise HTTPException(status_code=404, detail="Employment or work schedule not found")
    if employment.company_id != schedule.company_id:
        raise HTTPException(status_code=422, detail="Schedule belongs to another company")
    if payload.effective_to is not None and payload.effective_to < payload.effective_from:
        raise HTTPException(status_code=422, detail="effective_to must not precede effective_from")
    row = ScheduleAssignment(employment_id=employment_id, **payload.model_dump())
    session.add(row)
    await session.flush()
    await _audit(session, user, "schedule_assignment.create", "schedule_assignment", row.id, rid)
    await session.commit()
    return row


enrollments_router = APIRouter(prefix="/enrollment-requests", tags=["enrollment-requests"])


def _enrollment_out(row: EnrollmentRequest) -> EnrollmentRequestOut:
    return EnrollmentRequestOut(
        id=row.id,
        employment_id=row.employment_id,
        device_id=row.device_id,
        methods=list((row.methods or {}).get("requested", [])),
        status=row.status,
        requested_by=row.requested_by,
        approved_by=row.approved_by,
        completed_by=row.completed_by,
        note=row.note,
    )


@enrollments_router.get("", response_model=list[EnrollmentRequestOut])
async def list_enrollment_requests(
    employment_id: uuid.UUID | None = None,
    device_id: uuid.UUID | None = None,
    _user: User = Depends(deps.require_permission("enrollments.read")),
    session: AsyncSession = Depends(get_db),
) -> list[EnrollmentRequestOut]:
    query = select(EnrollmentRequest).order_by(EnrollmentRequest.created_at.desc()).limit(200)
    if employment_id:
        query = query.where(EnrollmentRequest.employment_id == employment_id)
    if device_id:
        query = query.where(EnrollmentRequest.device_id == device_id)
    return [_enrollment_out(row) for row in (await session.execute(query)).scalars()]


@enrollments_router.post("", response_model=EnrollmentRequestOut, status_code=201)
async def create_enrollment_request(
    payload: EnrollmentRequestIn,
    user: User = Depends(deps.require_permission("enrollments.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> EnrollmentRequestOut:
    employment = await session.get(Employment, payload.employment_id)
    device = await session.get(Device, payload.device_id)
    if employment is None or device is None:
        raise HTTPException(status_code=404, detail="Employment or device not found")
    if device.site_id is not None:
        site = await session.get(Site, device.site_id)
        if site is not None and site.company_id != employment.company_id:
            raise HTTPException(status_code=422, detail="Device belongs to another company")
    allowed_methods = {"face", "fingerprint", "palm", "card", "password"}
    methods = {method.lower() for method in payload.methods}
    if not methods.issubset(allowed_methods):
        raise HTTPException(status_code=422, detail="Unsupported enrollment method")
    row = EnrollmentRequest(
        employment_id=employment.id,
        device_id=device.id,
        methods={"requested": sorted(methods)},
        requested_by=user.id,
        note=payload.note,
    )
    session.add(row)
    await session.flush()
    await _audit(session, user, "enrollment_request.create", "enrollment_request", row.id, rid)
    await session.commit()
    return _enrollment_out(row)


@enrollments_router.patch("/{request_id}", response_model=EnrollmentRequestOut)
async def update_enrollment_request(
    request_id: uuid.UUID,
    payload: EnrollmentRequestStatusIn,
    user: User = Depends(deps.require_permission("enrollments.approve")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> EnrollmentRequestOut:
    row = await session.get(EnrollmentRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Enrollment request not found")
    row.status = payload.status
    if payload.note is not None:
        row.note = payload.note
    if payload.status == "approved":
        row.approved_by = user.id
    if payload.status == "completed":
        row.completed_by = user.id
    await _audit(session, user, "enrollment_request.update", "enrollment_request", row.id, rid)
    await session.commit()
    return _enrollment_out(row)
