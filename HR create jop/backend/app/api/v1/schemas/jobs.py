from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobCreate(BaseModel):
    title: str
    raw_description: str | None = None
    status: str = "draft"
    department: str | None = None
    location: str | None = None
    job_type: str | None = None
    experience: str | None = None
    requirements: list[str] = []
    required_skills: list[str] = []


class JobUpdate(BaseModel):
    title: str | None = None
    raw_description: str | None = None
    status: str | None = None
    department: str | None = None
    location: str | None = None
    job_type: str | None = None
    experience: str | None = None
    requirements: list[str] | None = None
    required_skills: list[str] | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    title: str
    raw_description: str | None
    status: str
    department: str | None = None
    location: str | None = None
    job_type: str | None = None
    experience: str | None = None
    requirements: list[str] | None = None
    required_skills: list[str] | None = None
    created_at: datetime
    updated_at: datetime
