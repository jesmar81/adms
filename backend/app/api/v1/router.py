"""Aggregate `/api/v1` router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.devices import router as devices_router
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
router.include_router(attendance_router)
router.include_router(device_users_router)
router.include_router(commands_router)
router.include_router(users_router)
router.include_router(audit_router)
