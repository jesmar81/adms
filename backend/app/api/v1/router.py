"""Aggregate `/api/v1` router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.hr import (
    companies_router,
    employments_router,
    enrollments_router,
    groups_router,
    holidays_router,
    people_router,
    schedules_router,
    sites_router,
)
from app.api.v1.reports import reports_router
from app.api.v1.resources import (
    attendance_router,
    audit_router,
    commands_router,
    device_users_router,
)
from app.api.v1.users import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(devices_router)
router.include_router(groups_router)
router.include_router(companies_router)
router.include_router(sites_router)
router.include_router(people_router)
router.include_router(employments_router)
router.include_router(schedules_router)
router.include_router(holidays_router)
router.include_router(enrollments_router)
router.include_router(attendance_router)
router.include_router(reports_router)
router.include_router(device_users_router)
router.include_router(commands_router)
router.include_router(users_router)
router.include_router(audit_router)
