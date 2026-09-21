"""Schedule-aware attendance reports for HR and payroll review."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import deps
from app.api.v1.schemas import (
    AbsenceReportOut,
    DailyArrivalReportOut,
    PunctualityReportOut,
    WeeklyCardDayOut,
    WeeklyCardReportOut,
)
from app.core.database import get_db
from app.models.device import AttendanceLog, DeviceUser
from app.models.hr import (
    Company,
    Employment,
    Holiday,
    Person,
    ScheduleAssignment,
    ScheduleSlot,
    WorkSchedule,
)
from app.models.user import User

reports_router = APIRouter(prefix="/reports", tags=["reports"])


def _worker_name(person: Person) -> str:
    return " ".join(
        part for part in (person.first_name, person.last_name, person.second_last_name) if part
    )


def _local_marks(marks: list[datetime], report_day: date, timezone: tzinfo) -> list[datetime]:
    return [
        mark.astimezone(timezone)
        for mark in marks
        if mark.astimezone(timezone).date() == report_day
    ]


async def _report_data(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    company_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
) -> tuple[
    list[tuple[Employment, Person, Company]],
    dict[uuid.UUID, list[ScheduleAssignment]],
    dict[uuid.UUID, WorkSchedule],
    dict[uuid.UUID, list[ScheduleSlot]],
    set[tuple[uuid.UUID, date]],
    dict[uuid.UUID, list[datetime]],
]:
    worker_query = (
        select(Employment, Person, Company)
        .join(Person, Employment.person_id == Person.id)
        .join(Company, Employment.company_id == Company.id)
        .where(
            Person.active.is_(True),
            Employment.started_on <= end_date,
            (Employment.ended_on.is_(None) | (Employment.ended_on >= start_date)),
        )
        .order_by(Person.last_name, Person.first_name, Employment.employee_number)
    )
    if company_id is not None:
        worker_query = worker_query.where(Employment.company_id == company_id)
    if person_id is not None:
        worker_query = worker_query.where(Employment.person_id == person_id)
    workers = list((await session.execute(worker_query)).tuples())
    employment_ids = [employment.id for employment, _, _ in workers]
    person_ids = list({person.id for _, person, _ in workers})
    company_ids = list({company.id for _, _, company in workers})
    if not employment_ids:
        return [], {}, {}, {}, set(), {}

    assignments = list(
        (
            await session.execute(
                select(ScheduleAssignment).where(
                    ScheduleAssignment.active.is_(True),
                    ScheduleAssignment.employment_id.in_(employment_ids),
                    ScheduleAssignment.effective_from <= end_date,
                    ScheduleAssignment.effective_to.is_(None)
                    | (ScheduleAssignment.effective_to >= start_date),
                )
            )
        ).scalars()
    )
    assignments_by_employment: dict[uuid.UUID, list[ScheduleAssignment]] = defaultdict(list)
    for assignment in assignments:
        assignments_by_employment[assignment.employment_id].append(assignment)
    schedule_ids = list({assignment.work_schedule_id for assignment in assignments})
    schedules: dict[uuid.UUID, WorkSchedule] = {}
    slots_by_schedule: dict[uuid.UUID, list[ScheduleSlot]] = defaultdict(list)
    if schedule_ids:
        schedules = {
            row.id: row
            for row in (
                await session.execute(select(WorkSchedule).where(WorkSchedule.id.in_(schedule_ids)))
            ).scalars()
        }
        for slot in (
            await session.execute(
                select(ScheduleSlot).where(ScheduleSlot.work_schedule_id.in_(schedule_ids))
            )
        ).scalars():
            slots_by_schedule[slot.work_schedule_id].append(slot)
    holidays = {
        (row.company_id, row.holiday_date)
        for row in (
            await session.execute(
                select(Holiday).where(
                    Holiday.company_id.in_(company_ids),
                    Holiday.holiday_date >= start_date,
                    Holiday.holiday_date <= end_date,
                )
            )
        ).scalars()
    }
    mark_start = datetime.combine(start_date, time.min, tzinfo=UTC) - timedelta(hours=14)
    mark_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC) + timedelta(
        hours=14
    )
    marks_by_person: dict[uuid.UUID, list[datetime]] = defaultdict(list)
    if person_ids:
        mark_rows = await session.execute(
            select(AttendanceLog.recorded_at, DeviceUser.person_id)
            .join(DeviceUser, AttendanceLog.device_user_id == DeviceUser.id)
            .where(
                DeviceUser.person_id.in_(person_ids),
                AttendanceLog.recorded_at >= mark_start,
                AttendanceLog.recorded_at < mark_end,
            )
            .order_by(AttendanceLog.recorded_at)
        )
        for recorded_at, mark_person_id in mark_rows.tuples():
            if mark_person_id is not None:
                marks_by_person[mark_person_id].append(recorded_at)
    return (
        workers,
        assignments_by_employment,
        schedules,
        slots_by_schedule,
        holidays,
        marks_by_person,
    )


def _assignment_for_day(
    assignments: list[ScheduleAssignment], report_day: date
) -> ScheduleAssignment | None:
    eligible = [
        item
        for item in assignments
        if item.effective_from <= report_day
        and (item.effective_to is None or item.effective_to >= report_day)
    ]
    return max(eligible, key=lambda item: item.effective_from, default=None)


def _scheduled_bounds(
    employment: Employment,
    report_day: date,
    assignments: list[ScheduleAssignment],
    schedules: dict[uuid.UUID, WorkSchedule],
    slots_by_schedule: dict[uuid.UUID, list[ScheduleSlot]],
    holidays: set[tuple[uuid.UUID, date]],
) -> tuple[datetime, datetime | None, int] | None:
    if report_day < employment.started_on or (
        employment.ended_on is not None and report_day > employment.ended_on
    ):
        return None
    if (employment.company_id, report_day) in holidays:
        return None
    assignment = _assignment_for_day(assignments, report_day)
    if assignment is None:
        return None
    schedule = schedules.get(assignment.work_schedule_id)
    if schedule is None:
        return None
    slots = [
        slot
        for slot in slots_by_schedule.get(schedule.id, [])
        if slot.day_of_week == report_day.weekday() and slot.required
    ]
    entries = [slot for slot in slots if slot.kind == "entry"]
    if not entries:
        return None
    exits = [slot for slot in slots if slot.kind == "exit"]
    timezone = ZoneInfo(schedule.timezone)
    entry = min(entries, key=lambda item: (item.expected_at, item.sequence))
    expected_entry = datetime.combine(report_day, entry.expected_at, tzinfo=timezone)
    expected_exit = (
        datetime.combine(
            report_day,
            max(exits, key=lambda item: (item.expected_at, item.sequence)).expected_at,
            tzinfo=timezone,
        )
        if exits
        else None
    )
    return expected_entry, expected_exit, entry.tolerance_minutes


@reports_router.get("/daily-arrivals", response_model=list[DailyArrivalReportOut])
async def daily_arrivals(
    company_id: uuid.UUID,
    report_date: date = Query(default_factory=date.today),
    _user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> list[DailyArrivalReportOut]:
    workers, assignments, schedules, slots, holidays, marks_by_person = await _report_data(
        session, report_date, report_date, company_id=company_id
    )
    result: list[DailyArrivalReportOut] = []
    for employment, person, company in workers:
        bounds = _scheduled_bounds(
            employment, report_date, assignments.get(employment.id, []), schedules, slots, holidays
        )
        timezone = (bounds[0].tzinfo or UTC) if bounds is not None else ZoneInfo(company.timezone)
        marks = _local_marks(marks_by_person.get(person.id, []), report_date, timezone)
        if marks:
            result.append(
                DailyArrivalReportOut(
                    person_id=person.id,
                    employment_id=employment.id,
                    worker_name=_worker_name(person),
                    employee_number=employment.employee_number,
                    company_name=company.legal_name,
                    report_date=report_date,
                    first_mark_at=marks[0],
                    mark_count=len(marks),
                )
            )
    return sorted(result, key=lambda item: (item.first_mark_at, item.worker_name))


@reports_router.get("/absences", response_model=list[AbsenceReportOut])
async def absences(
    company_id: uuid.UUID,
    report_date: date = Query(default_factory=date.today),
    _user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> list[AbsenceReportOut]:
    workers, assignments, schedules, slots, holidays, marks_by_person = await _report_data(
        session, report_date, report_date, company_id=company_id
    )
    now = datetime.now(UTC)
    result: list[AbsenceReportOut] = []
    for employment, person, company in workers:
        bounds = _scheduled_bounds(
            employment, report_date, assignments.get(employment.id, []), schedules, slots, holidays
        )
        if bounds is None:
            continue
        expected_entry, _, tolerance = bounds
        if report_date == datetime.now(expected_entry.tzinfo).date() and now < (
            expected_entry.astimezone(UTC) + timedelta(minutes=tolerance)
        ):
            continue
        marks = _local_marks(
            marks_by_person.get(person.id, []), report_date, expected_entry.tzinfo or UTC
        )
        if not marks:
            result.append(
                AbsenceReportOut(
                    person_id=person.id,
                    employment_id=employment.id,
                    worker_name=_worker_name(person),
                    employee_number=employment.employee_number,
                    company_name=company.legal_name,
                    report_date=report_date,
                    expected_entry_at=expected_entry,
                )
            )
    return result


@reports_router.get("/weekly-card", response_model=WeeklyCardReportOut)
async def weekly_card(
    person_id: uuid.UUID,
    week_start: date,
    _user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> WeeklyCardReportOut:
    if week_start.weekday() != 0:
        raise HTTPException(status_code=422, detail="week_start must be a Monday")
    week_end = week_start + timedelta(days=6)
    workers, _, schedules, _, _, marks_by_person = await _report_data(
        session, week_start, week_end, person_id=person_id
    )
    if not workers:
        raise HTTPException(
            status_code=404, detail="Worker not found or has no employment in this week"
        )
    person = workers[0][1]
    timezone = ZoneInfo(workers[0][2].timezone)
    days: list[WeeklyCardDayOut] = []
    for offset in range(7):
        report_day = week_start + timedelta(days=offset)
        marks = _local_marks(marks_by_person.get(person.id, []), report_day, timezone)
        days.append(
            WeeklyCardDayOut(
                report_date=report_day,
                first_mark_at=marks[0] if marks else None,
                last_mark_at=marks[-1] if marks else None,
                mark_count=len(marks),
            )
        )
    return WeeklyCardReportOut(
        person_id=person.id,
        worker_name=_worker_name(person),
        week_start=week_start,
        week_end=week_end,
        days=days,
    )


@reports_router.get("/punctuality", response_model=list[PunctualityReportOut])
async def punctuality(
    company_id: uuid.UUID,
    date_from: date,
    date_to: date,
    mode: str = Query(default="both", pattern="^(both|late|early)$"),
    _user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> list[PunctualityReportOut]:
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(status_code=422, detail="Use an ordered range of at most 366 days")
    workers, assignments, schedules, slots, holidays, marks_by_person = await _report_data(
        session, date_from, date_to, company_id=company_id
    )
    result: list[PunctualityReportOut] = []
    report_day = date_from
    while report_day <= date_to:
        for employment, person, company in workers:
            bounds = _scheduled_bounds(
                employment,
                report_day,
                assignments.get(employment.id, []),
                schedules,
                slots,
                holidays,
            )
            if bounds is None:
                continue
            expected_entry, expected_exit, tolerance = bounds
            marks = _local_marks(
                marks_by_person.get(person.id, []), report_day, expected_entry.tzinfo or UTC
            )
            if not marks:
                continue
            late_minutes = max(
                0, int((marks[0] - expected_entry).total_seconds() // 60) - tolerance
            )
            early_minutes = (
                max(0, int((expected_exit - marks[-1]).total_seconds() // 60))
                if expected_exit
                else 0
            )
            if (mode == "late" and late_minutes == 0) or (mode == "early" and early_minutes == 0):
                continue
            if mode == "both" and late_minutes == 0 and early_minutes == 0:
                continue
            result.append(
                PunctualityReportOut(
                    person_id=person.id,
                    employment_id=employment.id,
                    worker_name=_worker_name(person),
                    employee_number=employment.employee_number,
                    company_name=company.legal_name,
                    report_date=report_day,
                    expected_entry_at=expected_entry,
                    first_mark_at=marks[0],
                    late_minutes=late_minutes,
                    expected_exit_at=expected_exit,
                    last_mark_at=marks[-1],
                    early_departure_minutes=early_minutes,
                )
            )
        report_day += timedelta(days=1)
    return result
