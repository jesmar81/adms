"""Scheduled maintenance for company holiday calendars."""

from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import select

from app.core.database import get_session_factory
from app.models.hr import Company
from app.services.holidays import ensure_statutory_holidays
from app.workers.celery_app import celery_app


@celery_app.task(name="adms.ensure_statutory_holidays")  # type: ignore[untyped-decorator]
def ensure_statutory_holidays_task() -> dict[str, int]:
    """Create the current and next annual calendar for every active company."""

    async def run() -> dict[str, int]:
        created = 0
        current_year = date.today().year
        async with get_session_factory()() as session:
            result = await session.execute(select(Company.id).where(Company.active.is_(True)))
            company_ids = list(result.scalars())
            for company_id in company_ids:
                for year in (current_year, current_year + 1):
                    count, _ = await ensure_statutory_holidays(session, company_id, year)
                    created += count
            await session.commit()
        return {"companies": len(company_ids), "created": created}

    return asyncio.run(run())
