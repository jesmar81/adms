"""Statutory holiday rules and idempotent company-calendar generation."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hr import Holiday


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (occurrence - 1))


def mexican_statutory_holidays(year: int) -> list[tuple[date, str]]:
    """Known annual LFT art. 74 rules; electoral dates are entered manually."""
    holidays = [
        (date(year, 1, 1), "Año Nuevo"),
        (_nth_weekday(year, 2, 0, 1), "Conmemoración de la Constitución"),
        (_nth_weekday(year, 3, 0, 3), "Conmemoración del natalicio de Benito Juárez"),
        (date(year, 5, 1), "Día del Trabajo"),
        (date(year, 9, 16), "Aniversario de la Independencia"),
        (_nth_weekday(year, 11, 0, 3), "Conmemoración de la Revolución Mexicana"),
        (date(year, 12, 25), "Navidad"),
    ]
    if year >= 2024 and (year - 2024) % 6 == 0:
        holidays.append((date(year, 10, 1), "Transmisión del Poder Ejecutivo Federal"))
    return sorted(holidays)


async def ensure_statutory_holidays(
    session: AsyncSession, company_id: uuid.UUID, year: int
) -> tuple[int, int]:
    """Create missing legal dates without replacing HR-entered company dates."""
    statutory = mexican_statutory_holidays(year)
    existing_dates = set(
        (
            await session.execute(
                select(Holiday.holiday_date).where(
                    Holiday.company_id == company_id,
                    Holiday.holiday_date >= date(year, 1, 1),
                    Holiday.holiday_date <= date(year, 12, 31),
                )
            )
        ).scalars()
    )
    created = 0
    for holiday_date, name in statutory:
        if holiday_date in existing_dates:
            continue
        session.add(
            Holiday(
                company_id=company_id,
                holiday_date=holiday_date,
                name=name,
                kind="statutory",
                source="LFT_ART_74",
                is_paid_rest=True,
                generated=True,
            )
        )
        created += 1
    return created, len(statutory) - created
