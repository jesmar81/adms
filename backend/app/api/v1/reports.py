"""Schedule-aware reports, auditable HR adjustments and weekly-card PDFs."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import deps
from app.api.v1.schemas import (
    AbsenceReportOut,
    AttendanceAdjustmentIn,
    AttendanceAdjustmentOut,
    AttendanceDashboardOut,
    DailyArrivalReportOut,
    OvertimeAuthorizationIn,
    OvertimeManualIn,
    OvertimeRequestOut,
    OvertimeReviewIn,
    PunctualityReportOut,
    WeeklyCardDayOut,
    WeeklyCardReportOut,
)
from app.core.database import get_db
from app.models.device import AttendanceAttribution, AttendanceLog, Device
from app.models.hr import (
    Address,
    AttendanceAdjustment,
    Company,
    Employment,
    Holiday,
    OvertimeRequest,
    Person,
    ScheduleAssignment,
    ScheduleSlot,
    Site,
    WorkSchedule,
)
from app.models.user import User
from app.services import access as access_svc
from app.services import audit as audit_svc

reports_router = APIRouter(prefix="/reports", tags=["reports"])


def _worker_name(person: Person) -> str:
    return " ".join(
        part for part in (person.first_name, person.last_name, person.second_last_name) if part
    )


def _local_marks(marks: list[datetime], day: date, timezone: tzinfo) -> list[datetime]:
    return [mark.astimezone(timezone) for mark in marks if mark.astimezone(timezone).date() == day]


def _address(value: Address | None) -> str | None:
    if value is None:
        return None
    street = " ".join(part for part in (value.street, value.exterior_number) if part)
    if value.interior_number:
        street = f"{street} Int. {value.interior_number}".strip()
    values = (
        street,
        value.neighborhood,
        value.municipality,
        value.state,
        f"C.P. {value.postal_code}" if value.postal_code else None,
        value.country,
    )
    return ", ".join(part for part in values if part)


async def _data(
    session: AsyncSession,
    start: date,
    end: date,
    *,
    company_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    employment_id: uuid.UUID | None = None,
    allowed_company_ids: set[uuid.UUID] | None = None,
) -> tuple[
    list[tuple[Employment, Person, Company]],
    dict[uuid.UUID, list[ScheduleAssignment]],
    dict[uuid.UUID, WorkSchedule],
    dict[uuid.UUID, list[ScheduleSlot]],
    set[tuple[uuid.UUID, date]],
    dict[uuid.UUID, list[datetime]],
    dict[tuple[uuid.UUID, date], AttendanceAdjustment],
]:
    query = (
        select(Employment, Person, Company)
        .join(Person, Employment.person_id == Person.id)
        .join(Company, Employment.company_id == Company.id)
        .where(
            Employment.started_on <= end,
            Employment.ended_on.is_(None) | (Employment.ended_on >= start),
        )
        .order_by(
            Company.legal_name, Person.last_name, Person.first_name, Employment.employee_number
        )
    )
    if company_id:
        query = query.where(Employment.company_id == company_id)
    if allowed_company_ids is not None:
        query = query.where(Employment.company_id.in_(allowed_company_ids))
    if group_id:
        query = query.where(Company.corporate_group_id == group_id)
    if person_id:
        query = query.where(Employment.person_id == person_id)
    if employment_id:
        query = query.where(Employment.id == employment_id)
    workers = list((await session.execute(query)).tuples())
    employment_ids = [item[0].id for item in workers]
    if not employment_ids:
        return [], {}, {}, {}, set(), {}, {}
    company_ids = list({item[2].id for item in workers})
    assignments_rows = list(
        (
            await session.execute(
                select(ScheduleAssignment).where(
                    ScheduleAssignment.active.is_(True),
                    ScheduleAssignment.employment_id.in_(employment_ids),
                    ScheduleAssignment.effective_from <= end,
                    ScheduleAssignment.effective_to.is_(None)
                    | (ScheduleAssignment.effective_to >= start),
                )
            )
        ).scalars()
    )
    assignments: dict[uuid.UUID, list[ScheduleAssignment]] = defaultdict(list)
    for item in assignments_rows:
        assignments[item.employment_id].append(item)
    schedule_ids = list({item.work_schedule_id for item in assignments_rows})
    schedules = (
        {
            item.id: item
            for item in (
                await session.execute(select(WorkSchedule).where(WorkSchedule.id.in_(schedule_ids)))
            ).scalars()
        }
        if schedule_ids
        else {}
    )
    slots: dict[uuid.UUID, list[ScheduleSlot]] = defaultdict(list)
    if schedule_ids:
        slot_rows: list[ScheduleSlot] = list(
            (
                await session.execute(
                    select(ScheduleSlot).where(ScheduleSlot.work_schedule_id.in_(schedule_ids))
                )
            ).scalars()
        )
        for slot in slot_rows:
            slots[slot.work_schedule_id].append(slot)
    holidays = {
        (item.company_id, item.holiday_date)
        for item in (
            await session.execute(
                select(Holiday).where(
                    Holiday.company_id.in_(company_ids),
                    Holiday.holiday_date >= start,
                    Holiday.holiday_date <= end,
                )
            )
        ).scalars()
    }
    adjustments = {
        (item.employment_id, item.attendance_date): item
        for item in (
            await session.execute(
                select(AttendanceAdjustment).where(
                    AttendanceAdjustment.employment_id.in_(employment_ids),
                    AttendanceAdjustment.attendance_date >= start,
                    AttendanceAdjustment.attendance_date <= end,
                )
            )
        ).scalars()
    }
    marks: dict[uuid.UUID, list[datetime]] = defaultdict(list)
    mark_start = datetime.combine(start, time.min, tzinfo=UTC) - timedelta(hours=14)
    mark_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC) + timedelta(hours=14)
    rows = await session.execute(
        select(AttendanceLog.recorded_at, AttendanceAttribution.employment_id)
        .join(
            AttendanceAttribution,
            AttendanceAttribution.attendance_log_id == AttendanceLog.id,
        )
        .where(
            AttendanceAttribution.status == "assigned",
            AttendanceAttribution.employment_id.in_(employment_ids),
            AttendanceLog.recorded_at >= mark_start,
            AttendanceLog.recorded_at < mark_end,
        )
        .order_by(AttendanceLog.recorded_at)
    )
    for recorded_at, mark_employment_id in rows.tuples():
        if mark_employment_id:
            marks[mark_employment_id].append(recorded_at)
    return workers, assignments, schedules, slots, holidays, marks, adjustments


def _assignment(items: list[ScheduleAssignment], day: date) -> ScheduleAssignment | None:
    return max(
        (
            item
            for item in items
            if item.effective_from <= day
            and (item.effective_to is None or item.effective_to >= day)
        ),
        key=lambda item: item.effective_from,
        default=None,
    )


def _bounds(
    employment: Employment,
    day: date,
    assignments: list[ScheduleAssignment],
    schedules: dict[uuid.UUID, WorkSchedule],
    slots: dict[uuid.UUID, list[ScheduleSlot]],
    holidays: set[tuple[uuid.UUID, date]],
) -> tuple[datetime, datetime | None, int] | None:
    if (
        day < employment.started_on
        or (employment.ended_on and day > employment.ended_on)
        or (employment.company_id, day) in holidays
    ):
        return None
    assignment = _assignment(assignments, day)
    schedule = schedules.get(assignment.work_schedule_id) if assignment else None
    if not schedule:
        return None
    active = [
        item
        for item in slots.get(schedule.id, [])
        if item.day_of_week == day.weekday() and item.required
    ]
    entries = [item for item in active if item.kind == "entry"]
    if not entries:
        return None
    exits = [item for item in active if item.kind == "exit"]
    tz = ZoneInfo(schedule.timezone)
    entry = min(entries, key=lambda item: (item.expected_at, item.sequence))
    exit_at = (
        datetime.combine(
            day,
            max(exits, key=lambda item: (item.expected_at, item.sequence)).expected_at,
            tzinfo=tz,
        )
        if exits
        else None
    )
    return datetime.combine(day, entry.expected_at, tzinfo=tz), exit_at, entry.tolerance_minutes


def _raw_events(
    marks: list[datetime],
) -> tuple[datetime | None, datetime | None, datetime | None, datetime | None]:
    if len(marks) == 0:
        return None, None, None, None
    if len(marks) == 1:
        return marks[0], None, None, None
    if len(marks) == 2:
        return marks[0], None, None, marks[1]
    if len(marks) == 3:
        return marks[0], marks[1], None, marks[2]
    return marks[0], marks[1], marks[-2], marks[-1]


def _events(
    marks: list[datetime], adjustment: AttendanceAdjustment | None
) -> tuple[datetime | None, datetime | None, datetime | None, datetime | None]:
    entry, meal_out, meal_in, exit_at = _raw_events(marks)
    if adjustment is None:
        return entry, meal_out, meal_in, exit_at
    return (
        adjustment.entry_at or entry,
        adjustment.meal_out_at or meal_out,
        adjustment.meal_in_at or meal_in,
        adjustment.exit_at or exit_at,
    )


def _day(
    employment: Employment,
    report_day: date,
    assignments: list[ScheduleAssignment],
    schedules: dict[uuid.UUID, WorkSchedule],
    slots: dict[uuid.UUID, list[ScheduleSlot]],
    holidays: set[tuple[uuid.UUID, date]],
    marks: list[datetime],
    adjustment: AttendanceAdjustment | None,
) -> WeeklyCardDayOut:
    expected = _bounds(employment, report_day, assignments, schedules, slots, holidays)
    entry, meal_out, meal_in, exit_at = _events(marks, adjustment)
    kwargs: dict[str, Any] = {
        "report_date": report_day,
        "entry_at": entry,
        "meal_out_at": meal_out,
        "meal_in_at": meal_in,
        "exit_at": exit_at,
        "mark_count": len(marks),
        "adjustment_id": adjustment.id if adjustment else None,
        "adjustment_reason": adjustment.reason if adjustment else None,
    }
    if expected is None:
        if report_day < employment.started_on or (
            employment.ended_on and report_day > employment.ended_on
        ):
            return WeeklyCardDayOut.model_validate({"day_kind": "FUERA DE VIGENCIA", **kwargs})
        return WeeklyCardDayOut.model_validate(
            {
                "day_kind": "FERIADO"
                if (employment.company_id, report_day) in holidays
                else "DESCANSO",
                **kwargs,
            }
        )
    expected_entry, expected_exit, tolerance = expected
    if adjustment and adjustment.absence_kind:
        absence_label = "JUSTIFICADA" if adjustment.absence_kind == "justified" else "INJUSTIFICADA"
        return WeeklyCardDayOut.model_validate({"day_kind": f"FALTA {absence_label}", **kwargs})
    if entry is None:
        return WeeklyCardDayOut.model_validate({"day_kind": "FALTA INJUSTIFICADA", **kwargs})
    late = max(0, int((entry - expected_entry).total_seconds() // 60) - tolerance)
    early = (
        max(0, int((expected_exit - exit_at).total_seconds() // 60))
        if expected_exit and exit_at
        else 0
    )
    overtime = (
        max(0, int((exit_at - expected_exit).total_seconds() // 60))
        if expected_exit and exit_at
        else 0
    )
    incidents = []
    if late:
        incidents.append("RETARDO")
    if early:
        incidents.append("SALIDA FUERA DE HORARIO")
    if overtime:
        incidents.append("TIEMPO EXTRA DETECTADO")
    kind = "LABORADO CON " + " Y ".join(incidents) if incidents else "LABORAL"
    return WeeklyCardDayOut.model_validate(
        {
            "day_kind": kind,
            "late_minutes": late,
            "early_departure_minutes": early,
            "overtime_minutes": overtime,
            **kwargs,
        }
    )


async def _locations(
    session: AsyncSession, workers: list[tuple[Employment, Person, Company]]
) -> dict[uuid.UUID, tuple[str | None, str | None]]:
    site_ids = list({item[0].site_id for item in workers if item[0].site_id})
    company_ids = list({item[2].id for item in workers})
    sites = (
        {
            item.id: item
            for item in (await session.execute(select(Site).where(Site.id.in_(site_ids)))).scalars()
        }
        if site_ids
        else {}
    )
    addresses = list(
        (
            await session.execute(
                select(Address).where(
                    Address.site_id.in_(site_ids) | Address.company_id.in_(company_ids)
                )
            )
        ).scalars()
    )
    by_site = {item.site_id: item for item in addresses if item.site_id}
    by_company = {item.company_id: item for item in addresses if item.company_id}
    return {
        employment.id: (
            sites[employment.site_id].name if employment.site_id in sites else None,
            _address(
                by_site.get(employment.site_id)
                if employment.site_id
                else by_company.get(company.id)
            ),
        )
        for employment, _, company in workers
    }


def _card(
    worker: tuple[Employment, Person, Company],
    week_start: date,
    assignments: dict[uuid.UUID, list[ScheduleAssignment]],
    schedules: dict[uuid.UUID, WorkSchedule],
    slots: dict[uuid.UUID, list[ScheduleSlot]],
    holidays: set[tuple[uuid.UUID, date]],
    marks: dict[uuid.UUID, list[datetime]],
    adjustments: dict[tuple[uuid.UUID, date], AttendanceAdjustment],
    locations: dict[uuid.UUID, tuple[str | None, str | None]],
) -> WeeklyCardReportOut:
    employment, person, company = worker
    site_name, address = locations.get(employment.id, (None, None))
    employment_assignments = assignments.get(employment.id, [])
    days: list[WeeklyCardDayOut] = []
    for offset in range(7):
        report_day = week_start + timedelta(days=offset)
        assignment = _assignment(employment_assignments, report_day)
        schedule = schedules.get(assignment.work_schedule_id) if assignment else None
        timezone = ZoneInfo(schedule.timezone if schedule else company.timezone)
        days.append(
            _day(
                employment,
                report_day,
                employment_assignments,
                schedules,
                slots,
                holidays,
                _local_marks(marks.get(employment.id, []), report_day, timezone),
                adjustments.get((employment.id, report_day)),
            )
        )
    return WeeklyCardReportOut(
        employment_id=employment.id,
        person_id=person.id,
        worker_name=_worker_name(person),
        employee_number=employment.employee_number,
        company_name=company.legal_name,
        site_name=site_name,
        address=address,
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        days=days,
    )


@reports_router.get("/dashboard", response_model=AttendanceDashboardOut)
async def attendance_dashboard(
    company_id: uuid.UUID,
    report_date: date = Query(
        default_factory=lambda: datetime.now(ZoneInfo("America/Mexico_City")).date()
    ),
    user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> AttendanceDashboardOut:
    """Return schedule-aware executive metrics without treating raw marks as payroll facts."""
    company = await access_svc.require_company(session, user, company_id)
    workers, assignments, schedules, slots, holidays, marks, adjustments = await _data(
        session,
        report_date,
        report_date,
        company_id=company_id,
        allowed_company_ids=await access_svc.company_ids(session, user),
    )
    scheduled_workers = present_workers = on_time_workers = late_workers = late_minutes = 0
    absent_workers = justified_absences = 0
    for employment, _, _ in workers:
        expected = _bounds(
            employment,
            report_date,
            assignments.get(employment.id, []),
            schedules,
            slots,
            holidays,
        )
        if expected is None:
            continue
        scheduled_workers += 1
        adjustment = adjustments.get((employment.id, report_date))
        if adjustment and adjustment.absence_kind:
            absent_workers += 1
            justified_absences += int(adjustment.absence_kind == "justified")
            continue
        entry, _, _, _ = _events(
            _local_marks(marks.get(employment.id, []), report_date, expected[0].tzinfo or UTC),
            adjustment,
        )
        if entry is None:
            absent_workers += 1
            continue
        present_workers += 1
        delay = max(0, int((entry - expected[0]).total_seconds() // 60) - expected[2])
        if delay:
            late_workers += 1
            late_minutes += delay
        else:
            on_time_workers += 1

    timezone = ZoneInfo(company.timezone)
    mark_start = datetime.combine(report_date, time.min, tzinfo=timezone).astimezone(UTC)
    next_day_start = datetime.combine(report_date + timedelta(days=1), time.min, tzinfo=timezone)
    mark_end = next_day_start.astimezone(UTC)
    company_device_ids = (
        select(Device.id).join(Site, Device.site_id == Site.id).where(Site.company_id == company_id)
    )
    raw_marks = (
        await session.scalar(
            select(func.count())
            .select_from(AttendanceLog)
            .where(
                AttendanceLog.device_id.in_(company_device_ids),
                AttendanceLog.recorded_at >= mark_start,
                AttendanceLog.recorded_at < mark_end,
            )
        )
        or 0
    )
    unresolved_marks = (
        await session.scalar(
            select(func.count())
            .select_from(AttendanceAttribution)
            .join(AttendanceLog, AttendanceAttribution.attendance_log_id == AttendanceLog.id)
            .where(
                AttendanceLog.device_id.in_(company_device_ids),
                AttendanceLog.recorded_at >= mark_start,
                AttendanceLog.recorded_at < mark_end,
                AttendanceAttribution.status.in_(("ambiguous", "unassigned")),
            )
        )
        or 0
    )
    overtime_rows = (
        await session.execute(
            select(
                OvertimeRequest.status,
                func.count(OvertimeRequest.id),
                func.coalesce(func.sum(OvertimeRequest.authorized_minutes), 0),
            )
            .join(Employment, OvertimeRequest.employment_id == Employment.id)
            .where(
                Employment.company_id == company_id,
                OvertimeRequest.attendance_date == report_date,
            )
            .group_by(OvertimeRequest.status)
        )
    ).all()
    overtime = {status: (count, int(minutes)) for status, count, minutes in overtime_rows}
    return AttendanceDashboardOut(
        company_id=company_id,
        report_date=report_date,
        scheduled_workers=scheduled_workers,
        present_workers=present_workers,
        on_time_workers=on_time_workers,
        late_workers=late_workers,
        late_minutes=late_minutes,
        absent_workers=absent_workers,
        justified_absences=justified_absences,
        raw_marks=raw_marks,
        unresolved_marks=unresolved_marks,
        overtime_pending_hr=overtime.get("pending_hr", (0, 0))[0],
        overtime_pending_direction=overtime.get("pending_direction", (0, 0))[0],
        overtime_authorized_minutes=overtime.get("approved", (0, 0))[1],
    )


@reports_router.get("/daily-arrivals", response_model=list[DailyArrivalReportOut])
async def daily_arrivals(
    company_id: uuid.UUID,
    report_date: date = Query(default_factory=date.today),
    user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> list[DailyArrivalReportOut]:
    await access_svc.require_company(session, user, company_id)
    workers, assignments, schedules, slots, holidays, marks, adjustments = await _data(
        session,
        report_date,
        report_date,
        company_id=company_id,
        allowed_company_ids=await access_svc.company_ids(session, user),
    )
    result: list[DailyArrivalReportOut] = []
    for employment, person, company in workers:
        expected = _bounds(
            employment, report_date, assignments.get(employment.id, []), schedules, slots, holidays
        )
        timezone = expected[0].tzinfo if expected else ZoneInfo(company.timezone)
        entry, _, _, _ = _events(
            _local_marks(marks.get(employment.id, []), report_date, timezone or UTC),
            adjustments.get((employment.id, report_date)),
        )
        if entry:
            result.append(
                DailyArrivalReportOut(
                    person_id=person.id,
                    employment_id=employment.id,
                    worker_name=_worker_name(person),
                    employee_number=employment.employee_number,
                    company_name=company.legal_name,
                    report_date=report_date,
                    first_mark_at=entry,
                    mark_count=len(
                        _local_marks(marks.get(employment.id, []), report_date, timezone or UTC)
                    ),
                )
            )
    return sorted(result, key=lambda item: (item.first_mark_at, item.worker_name))


@reports_router.get("/absences", response_model=list[AbsenceReportOut])
async def absences(
    company_id: uuid.UUID,
    report_date: date = Query(default_factory=date.today),
    user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> list[AbsenceReportOut]:
    await access_svc.require_company(session, user, company_id)
    workers, assignments, schedules, slots, holidays, marks, adjustments = await _data(
        session,
        report_date,
        report_date,
        company_id=company_id,
        allowed_company_ids=await access_svc.company_ids(session, user),
    )
    result: list[AbsenceReportOut] = []
    for employment, person, company in workers:
        expected = _bounds(
            employment, report_date, assignments.get(employment.id, []), schedules, slots, holidays
        )
        if expected is None:
            continue
        adjustment = adjustments.get((employment.id, report_date))
        entry, _, _, _ = _events(
            _local_marks(marks.get(employment.id, []), report_date, expected[0].tzinfo or UTC),
            adjustment,
        )
        if entry is None or adjustment and adjustment.absence_kind:
            result.append(
                AbsenceReportOut(
                    person_id=person.id,
                    employment_id=employment.id,
                    worker_name=_worker_name(person),
                    employee_number=employment.employee_number,
                    company_name=company.legal_name,
                    report_date=report_date,
                    expected_entry_at=expected[0],
                )
            )
    return result


@reports_router.get("/weekly-card", response_model=WeeklyCardReportOut)
async def weekly_card(
    week_start: date,
    employment_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> WeeklyCardReportOut:
    if week_start.weekday() != 0:
        raise HTTPException(status_code=422, detail="week_start must be a Monday")
    if employment_id is None and person_id is None:
        raise HTTPException(status_code=422, detail="employment_id or person_id is required")
    if employment_id is not None:
        await access_svc.require_employment(session, user, employment_id)
    if person_id is not None:
        await access_svc.require_person(session, user, person_id)
    workers, assignments, schedules, slots, holidays, marks, adjustments = await _data(
        session,
        week_start,
        week_start + timedelta(days=6),
        person_id=person_id,
        employment_id=employment_id,
        allowed_company_ids=await access_svc.company_ids(session, user),
    )
    if not workers:
        raise HTTPException(status_code=404, detail="Worker not found or inactive in this week")
    return _card(
        workers[0],
        week_start,
        assignments,
        schedules,
        slots,
        holidays,
        marks,
        adjustments,
        await _locations(session, workers),
    )


@reports_router.get("/punctuality", response_model=list[PunctualityReportOut])
async def punctuality(
    company_id: uuid.UUID,
    date_from: date,
    date_to: date,
    mode: Literal["both", "late", "early"] = "both",
    user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> list[PunctualityReportOut]:
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(status_code=422, detail="Use an ordered range of at most 366 days")
    await access_svc.require_company(session, user, company_id)
    workers, assignments, schedules, slots, holidays, marks, adjustments = await _data(
        session,
        date_from,
        date_to,
        company_id=company_id,
        allowed_company_ids=await access_svc.company_ids(session, user),
    )
    result: list[PunctualityReportOut] = []
    day = date_from
    while day <= date_to:
        for employment, person, company in workers:
            expected = _bounds(
                employment, day, assignments.get(employment.id, []), schedules, slots, holidays
            )
            adjustment = adjustments.get((employment.id, day))
            if expected is None or adjustment and adjustment.absence_kind:
                continue
            entry, _, _, exit_at = _events(
                _local_marks(marks.get(employment.id, []), day, expected[0].tzinfo or UTC),
                adjustment,
            )
            if entry is None:
                continue
            late = max(0, int((entry - expected[0]).total_seconds() // 60) - expected[2])
            early = (
                max(0, int((expected[1] - exit_at).total_seconds() // 60))
                if expected[1] and exit_at
                else 0
            )
            if (
                (mode == "late" and not late)
                or (mode == "early" and not early)
                or (mode == "both" and not late and not early)
            ):
                continue
            result.append(
                PunctualityReportOut(
                    person_id=person.id,
                    employment_id=employment.id,
                    worker_name=_worker_name(person),
                    employee_number=employment.employee_number,
                    company_name=company.legal_name,
                    report_date=day,
                    expected_entry_at=expected[0],
                    first_mark_at=entry,
                    late_minutes=late,
                    expected_exit_at=expected[1],
                    last_mark_at=exit_at,
                    early_departure_minutes=early,
                )
            )
        day += timedelta(days=1)
    return result


def _overtime_out(
    request: OvertimeRequest, employment: Employment, person: Person, company: Company
) -> OvertimeRequestOut:
    return OvertimeRequestOut(
        id=request.id,
        person_id=person.id,
        employment_id=employment.id,
        worker_name=_worker_name(person),
        employee_number=employment.employee_number,
        company_name=company.legal_name,
        report_date=request.attendance_date,
        source=cast(Literal["detected", "manual"], request.source),
        status=cast(
            Literal["pending_hr", "pending_direction", "approved", "rejected", "cancelled"],
            request.status,
        ),
        scheduled_exit_at=request.scheduled_exit_at,
        detected_exit_at=request.detected_exit_at,
        minutes=request.minutes,
        reviewed_minutes=request.reviewed_minutes,
        authorized_minutes=request.authorized_minutes,
        reason=request.reason,
        review_note=request.review_note,
        authorization_note=request.authorization_note,
        created_at=request.created_at,
        reviewed_at=request.reviewed_at,
        authorized_at=request.authorized_at,
    )


async def _overtime_context(
    session: AsyncSession, request_id: uuid.UUID, user: User
) -> tuple[OvertimeRequest, Employment, Person, Company]:
    row = (
        await session.execute(
            select(OvertimeRequest, Employment, Person, Company)
            .join(Employment, OvertimeRequest.employment_id == Employment.id)
            .join(Person, Employment.person_id == Person.id)
            .join(Company, Employment.company_id == Company.id)
            .where(OvertimeRequest.id == request_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Overtime request not found")
    request, employment, person, company = row
    await access_svc.require_company(session, user, company.id)
    return request, employment, person, company


@reports_router.get("/overtime", response_model=list[OvertimeRequestOut])
async def list_overtime(
    company_id: uuid.UUID,
    date_from: date,
    date_to: date,
    user: User = Depends(deps.require_permission("overtime.read")),
    session: AsyncSession = Depends(get_db),
) -> list[OvertimeRequestOut]:
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(status_code=422, detail="Use an ordered range of at most 366 days")
    await access_svc.require_company(session, user, company_id)
    rows = (
        await session.execute(
            select(OvertimeRequest, Employment, Person, Company)
            .join(Employment, OvertimeRequest.employment_id == Employment.id)
            .join(Person, Employment.person_id == Person.id)
            .join(Company, Employment.company_id == Company.id)
            .where(
                Employment.company_id == company_id,
                OvertimeRequest.attendance_date >= date_from,
                OvertimeRequest.attendance_date <= date_to,
            )
            .order_by(OvertimeRequest.attendance_date.desc(), Person.last_name, Person.first_name)
        )
    ).tuples()
    return [
        _overtime_out(request, employment, person, company)
        for request, employment, person, company in rows
    ]


@reports_router.post("/overtime/detect", response_model=list[OvertimeRequestOut], status_code=201)
async def detect_overtime(
    company_id: uuid.UUID,
    date_from: date,
    date_to: date,
    user: User = Depends(deps.require_permission("overtime.request")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> list[OvertimeRequestOut]:
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(status_code=422, detail="Use an ordered range of at most 366 days")
    await access_svc.require_company(session, user, company_id)
    workers, assignments, schedules, slots, holidays, marks, adjustments = await _data(
        session,
        date_from,
        date_to,
        company_id=company_id,
        allowed_company_ids=await access_svc.company_ids(session, user),
    )
    employment_ids = [employment.id for employment, _, _ in workers]
    existing = (
        set(
            (
                await session.execute(
                    select(OvertimeRequest.employment_id, OvertimeRequest.attendance_date).where(
                        OvertimeRequest.employment_id.in_(employment_ids),
                        OvertimeRequest.attendance_date >= date_from,
                        OvertimeRequest.attendance_date <= date_to,
                    )
                )
            ).tuples()
        )
        if employment_ids
        else set()
    )
    created: list[tuple[OvertimeRequest, Employment, Person, Company]] = []
    report_day = date_from
    while report_day <= date_to:
        for employment, person, company in workers:
            if (employment.id, report_day) in existing:
                continue
            expected = _bounds(
                employment,
                report_day,
                assignments.get(employment.id, []),
                schedules,
                slots,
                holidays,
            )
            adjustment = adjustments.get((employment.id, report_day))
            if expected is None or expected[1] is None or (adjustment and adjustment.absence_kind):
                continue
            # Only terminal evidence later than the scheduled exit creates a candidate.
            raw_marks = _local_marks(
                marks.get(employment.id, []), report_day, expected[0].tzinfo or UTC
            )
            _, _, _, detected_exit = _raw_events(raw_marks)
            if detected_exit is None or detected_exit <= expected[1]:
                continue
            minutes = int((detected_exit - expected[1]).total_seconds() // 60)
            if minutes <= 0:
                continue
            request = OvertimeRequest(
                employment_id=employment.id,
                attendance_date=report_day,
                source="detected",
                status="pending_hr",
                scheduled_exit_at=expected[1],
                detected_exit_at=detected_exit,
                minutes=minutes,
                reason="Marca posterior a la salida programada; pendiente de revisión de RR. HH.",
                created_by=user.id,
            )
            session.add(request)
            created.append((request, employment, person, company))
        report_day += timedelta(days=1)
    await session.flush()
    for request, _, _, _ in created:
        await audit_svc.record(
            session,
            action="overtime.detect",
            user_id=user.id,
            resource_type="overtime_request",
            resource_id=request.id,
            request_id=rid,
            metadata={"source": "terminal_mark", "minutes": request.minutes},
        )
    await session.commit()
    return [
        _overtime_out(request, employment, person, company)
        for request, employment, person, company in created
    ]


@reports_router.post("/overtime/manual", response_model=OvertimeRequestOut, status_code=201)
async def create_manual_overtime(
    payload: OvertimeManualIn,
    user: User = Depends(deps.require_permission("overtime.request")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> OvertimeRequestOut:
    await access_svc.require_employment(session, user, payload.employment_id)
    workers, assignments, schedules, slots, holidays, marks, adjustments = await _data(
        session,
        payload.attendance_date,
        payload.attendance_date,
        employment_id=payload.employment_id,
        allowed_company_ids=await access_svc.company_ids(session, user),
    )
    if not workers:
        raise HTTPException(
            status_code=422, detail="Employment is not active on the requested date"
        )
    employment, person, company = workers[0]
    expected = _bounds(
        employment,
        payload.attendance_date,
        assignments.get(employment.id, []),
        schedules,
        slots,
        holidays,
    )
    adjustment = adjustments.get((employment.id, payload.attendance_date))
    if expected is None or expected[1] is None or (adjustment and adjustment.absence_kind):
        raise HTTPException(
            status_code=422, detail="A working day with a scheduled exit is required"
        )
    raw_marks = _local_marks(
        marks.get(employment.id, []), payload.attendance_date, expected[0].tzinfo or UTC
    )
    _, _, _, detected_exit = _raw_events(raw_marks)
    if detected_exit is not None and detected_exit > expected[1]:
        raise HTTPException(
            status_code=409,
            detail=(
                "A post-shift terminal mark exists; detect it instead of creating manual overtime"
            ),
        )
    existing = await session.scalar(
        select(OvertimeRequest).where(
            OvertimeRequest.employment_id == employment.id,
            OvertimeRequest.attendance_date == payload.attendance_date,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="An overtime request already exists for this worker-day"
        )
    request = OvertimeRequest(
        employment_id=employment.id,
        attendance_date=payload.attendance_date,
        source="manual",
        status="pending_hr",
        scheduled_exit_at=expected[1],
        minutes=payload.minutes,
        reason=payload.reason.strip(),
        created_by=user.id,
    )
    session.add(request)
    await session.flush()
    await audit_svc.record(
        session,
        action="overtime.manual_create",
        user_id=user.id,
        resource_type="overtime_request",
        resource_id=request.id,
        request_id=rid,
        metadata={"minutes": request.minutes},
    )
    await session.commit()
    await session.refresh(request)
    return _overtime_out(request, employment, person, company)


@reports_router.post("/overtime/{overtime_id}/review", response_model=OvertimeRequestOut)
async def review_overtime(
    overtime_id: uuid.UUID,
    payload: OvertimeReviewIn,
    user: User = Depends(deps.require_permission("overtime.review")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> OvertimeRequestOut:
    request, employment, person, company = await _overtime_context(session, overtime_id, user)
    if request.status != "pending_hr":
        raise HTTPException(status_code=409, detail="Overtime request is not pending HR review")
    if request.created_by == user.id:
        raise HTTPException(
            status_code=409, detail="Requester cannot review the same overtime request"
        )
    if payload.decision == "send_to_direction" and payload.reviewed_minutes is None:
        raise HTTPException(
            status_code=422, detail="Reviewed minutes are required before direction approval"
        )
    if payload.decision == "reject" and payload.reviewed_minutes is not None:
        raise HTTPException(
            status_code=422, detail="Rejected requests cannot include reviewed minutes"
        )
    request.reviewed_by = user.id
    request.reviewed_at = datetime.now(UTC)
    request.review_note = payload.note.strip()
    request.reviewed_minutes = payload.reviewed_minutes
    request.status = "pending_direction" if payload.decision == "send_to_direction" else "rejected"
    await audit_svc.record(
        session,
        action="overtime.hr_review",
        user_id=user.id,
        resource_type="overtime_request",
        resource_id=request.id,
        request_id=rid,
        metadata={"decision": payload.decision, "reviewed_minutes": payload.reviewed_minutes},
    )
    await session.commit()
    await session.refresh(request)
    return _overtime_out(request, employment, person, company)


@reports_router.post("/overtime/{overtime_id}/authorize", response_model=OvertimeRequestOut)
async def authorize_overtime(
    overtime_id: uuid.UUID,
    payload: OvertimeAuthorizationIn,
    user: User = Depends(deps.require_permission("overtime.approve")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> OvertimeRequestOut:
    request, employment, person, company = await _overtime_context(session, overtime_id, user)
    if request.status != "pending_direction":
        raise HTTPException(
            status_code=409, detail="Overtime request is not pending direction approval"
        )
    if user.id in {request.created_by, request.reviewed_by}:
        raise HTTPException(
            status_code=409, detail="Requester or HR reviewer cannot authorize overtime"
        )
    if payload.decision == "approve":
        if payload.authorized_minutes is None:
            raise HTTPException(status_code=422, detail="Authorized minutes are required")
        if (
            request.reviewed_minutes is None
            or payload.authorized_minutes > request.reviewed_minutes
        ):
            raise HTTPException(
                status_code=422, detail="Authorized minutes cannot exceed the HR review"
            )
    elif payload.authorized_minutes is not None:
        raise HTTPException(
            status_code=422, detail="Rejected requests cannot include authorized minutes"
        )
    request.authorized_by = user.id
    request.authorized_at = datetime.now(UTC)
    request.authorization_note = payload.note.strip()
    request.authorized_minutes = payload.authorized_minutes
    request.status = "approved" if payload.decision == "approve" else "rejected"
    await audit_svc.record(
        session,
        action="overtime.direction_authorize",
        user_id=user.id,
        resource_type="overtime_request",
        resource_id=request.id,
        request_id=rid,
        metadata={"decision": payload.decision, "authorized_minutes": payload.authorized_minutes},
    )
    await session.commit()
    await session.refresh(request)
    return _overtime_out(request, employment, person, company)


def _validate_adjustment(payload: AttendanceAdjustmentIn) -> None:
    times = [payload.entry_at, payload.meal_out_at, payload.meal_in_at, payload.exit_at]
    if payload.absence_kind and any(times):
        raise HTTPException(
            status_code=422, detail="An absence cannot also contain attendance times"
        )
    if not payload.absence_kind and not any(times):
        raise HTTPException(
            status_code=422, detail="Provide at least one time or an absence classification"
        )
    values = [value for value in times if value]
    if any(value.tzinfo is None for value in values) or any(
        first >= second for first, second in zip(values, values[1:], strict=False)
    ):
        raise HTTPException(
            status_code=422, detail="Attendance times must include timezone and be chronological"
        )


@reports_router.get("/adjustments", response_model=list[AttendanceAdjustmentOut])
async def list_adjustments(
    employment_id: uuid.UUID,
    date_from: date,
    date_to: date,
    user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> list[AttendanceAdjustment]:
    await access_svc.require_employment(session, user, employment_id)
    return list(
        (
            await session.execute(
                select(AttendanceAdjustment)
                .where(
                    AttendanceAdjustment.employment_id == employment_id,
                    AttendanceAdjustment.attendance_date >= date_from,
                    AttendanceAdjustment.attendance_date <= date_to,
                )
                .order_by(AttendanceAdjustment.attendance_date)
            )
        ).scalars()
    )


@reports_router.put("/adjustments/{employment_id}", response_model=AttendanceAdjustmentOut)
async def save_adjustment(
    employment_id: uuid.UUID,
    payload: AttendanceAdjustmentIn,
    user: User = Depends(deps.require_permission("attendance.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> AttendanceAdjustment:
    _validate_adjustment(payload)
    await access_svc.require_employment(session, user, employment_id)
    row = await session.scalar(
        select(AttendanceAdjustment).where(
            AttendanceAdjustment.employment_id == employment_id,
            AttendanceAdjustment.attendance_date == payload.attendance_date,
        )
    )
    values = payload.model_dump()
    if row is None:
        row = AttendanceAdjustment(
            employment_id=employment_id, created_by=user.id, updated_by=user.id, **values
        )
        session.add(row)
        action = "attendance_adjustment.create"
    else:
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_by = user.id
        action = "attendance_adjustment.update"
    await session.flush()
    await audit_svc.record(
        session,
        action=action,
        user_id=user.id,
        resource_type="attendance_adjustment",
        resource_id=row.id,
        request_id=rid,
        metadata={
            "employment_id": str(employment_id),
            "attendance_date": payload.attendance_date.isoformat(),
            "absence_kind": payload.absence_kind,
        },
    )
    await session.commit()
    await session.refresh(row)
    return row


def _pdf_text(value: str) -> str:
    return value.encode("cp1252", "replace").hex().upper()


def _pdf_page(card: WeeklyCardReportOut) -> bytes:
    commands: list[str] = ["0.2 w"]

    def text(x: int, y: int, value: str, size: int = 9) -> None:
        commands.append(f"BT /F1 {size} Tf {x} {y} Td <{_pdf_text(value[:110])}> Tj ET")

    text(70, 800, card.company_name.upper(), 17)
    text(70, 782, card.site_name or "CENTRO DE TRABAJO", 11)
    if card.address:
        text(70, 767, card.address, 8)
    commands.append("42 753 m 553 753 l S")
    text(42, 733, "TARJETA SEMANAL DE ASISTENCIA", 13)
    text(42, 716, f"Trabajador: {card.worker_name}", 10)
    text(330, 716, f"No. empleado: {card.employee_number}", 10)
    text(
        42,
        701,
        f"Semana: {card.week_start.isoformat()} al {card.week_end.isoformat()} (lunes a domingo)",
        9,
    )
    for x, label in (
        (42, "Día"),
        (105, "Clasificación"),
        (245, "Entrada"),
        (300, "Salida comida"),
        (378, "Regreso comida"),
        (462, "Salida"),
        (520, "Extra"),
    ):
        text(x, 678, label, 8)
    y = 649
    names = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    for index, day in enumerate(card.days):
        text(42, y, f"{names[index]} {day.report_date.strftime('%d/%m')}", 8)
        text(105, y, day.day_kind, 7)
        for x, value in (
            (245, day.entry_at),
            (323, day.meal_out_at),
            (405, day.meal_in_at),
            (474, day.exit_at),
        ):
            text(x, y, value.strftime("%H:%M") if value else "—", 8)
        text(520, y, f"{day.overtime_minutes} min" if day.overtime_minutes else "—", 7)
        if day.late_minutes or day.early_departure_minutes or day.overtime_minutes:
            text(
                105,
                y - 11,
                "Retardo: "
                f"{day.late_minutes} min; salida fuera de horario: "
                f"{day.early_departure_minutes} min; tiempo extra detectado: "
                f"{day.overtime_minutes} min",
                7,
            )
        commands.append(f"42 {y - 18} m 553 {y - 18} l S")
        y -= 31
    text(
        42,
        115,
        "Checadas del reloj: evidencia; ajustes de RR. HH.: auditables.",
        7,
    )
    text(70, 72, "Firma del trabajador", 8)
    text(380, 72, "Revisión de RR. HH.", 8)
    commands.append("70 82 m 240 82 l S 370 82 m 540 82 l S")
    return "\n".join(commands).encode("ascii")


def _pdf(cards: list[WeeklyCardReportOut]) -> bytes:
    content = [_pdf_page(card) for card in cards]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{4 + i * 2} 0 R".encode() for i in range(len(content)))
        + f"] /Count {len(content)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i, item in enumerate(content):
        stream = 5 + i * 2
        objects.extend(
            [
                (
                    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    "/Resources << /Font << /F1 3 0 R >> >> "
                    f"/Contents {stream} 0 R >>"
                ).encode(),
                b"<< /Length " + str(len(item)).encode() + b" >>\nstream\n" + item + b"\nendstream",
            ]
        )
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, item in enumerate(objects, 1):
        offsets.append(len(out))
        out.extend(f"{number} 0 obj\n".encode() + item + b"\nendobj\n")
    start = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    out.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )
    return bytes(out)


@reports_router.get("/weekly-cards.pdf")
async def weekly_cards_pdf(
    week_start: date,
    company_id: uuid.UUID | None = None,
    corporate_group_id: uuid.UUID | None = None,
    employment_id: uuid.UUID | None = None,
    user: User = Depends(deps.require_permission("attendance.export")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Response:
    if week_start.weekday() != 0:
        raise HTTPException(status_code=422, detail="week_start must be a Monday")
    if sum(value is not None for value in (company_id, corporate_group_id, employment_id)) != 1:
        raise HTTPException(
            status_code=422, detail="Select exactly one company, group or employment"
        )
    if company_id is not None:
        await access_svc.require_company(session, user, company_id)
    if corporate_group_id is not None:
        await access_svc.require_group(session, user, corporate_group_id)
    if employment_id is not None:
        await access_svc.require_employment(session, user, employment_id)
    workers, assignments, schedules, slots, holidays, marks, adjustments = await _data(
        session,
        week_start,
        week_start + timedelta(days=6),
        company_id=company_id,
        group_id=corporate_group_id,
        employment_id=employment_id,
        allowed_company_ids=await access_svc.company_ids(session, user),
    )
    if not workers:
        raise HTTPException(status_code=404, detail="No workers found for this selection and week")
    locations = await _locations(session, workers)
    cards = [
        _card(
            worker,
            week_start,
            assignments,
            schedules,
            slots,
            holidays,
            marks,
            adjustments,
            locations,
        )
        for worker in workers
    ]
    await audit_svc.record(
        session,
        action="attendance.weekly_cards.export",
        user_id=user.id,
        resource_type="attendance_report",
        request_id=rid,
        metadata={
            "week_start": week_start.isoformat(),
            "company_id": str(company_id) if company_id else None,
            "corporate_group_id": str(corporate_group_id) if corporate_group_id else None,
            "employment_id": str(employment_id) if employment_id else None,
            "card_count": len(cards),
        },
    )
    await session.commit()
    return Response(
        content=_pdf(cards),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="tarjetas_{week_start.isoformat()}.pdf"'
        },
    )
