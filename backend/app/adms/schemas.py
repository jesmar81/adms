"""Pydantic schemas for ADMS-adjacent API I/O (admin command intake)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CommandCreate(BaseModel):
    command_type: str = Field(description="One of CommandType values (whitelist)")
    params: dict[str, str] = Field(default_factory=dict)
