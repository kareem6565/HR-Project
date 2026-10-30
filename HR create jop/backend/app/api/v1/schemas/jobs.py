from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    raw_description: str | None = None
    description_text: str | None = None
    status: str = "draft"
    department: str | None = None
    location: str | None = None
    job_type: str | None = None
    experience: str | None = None
    requirements: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Job title is required.")
        return value


class JobUpdate(BaseModel):
    title: str | None = None
    raw_description: str | None = None
    description_text: str | None = None
    status: str | None = None
    department: str | None = None
    location: str | None = None
    job_type: str | None = None
    experience: str | None = None
    requirements: list[str] | None = None
    required_skills: list[str] | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Job title is required.")
        return value


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    title: str
    raw_description: str | None
    description_text: str | None = None
    status: str
    department: str | None = None
    location: str | None = None
    job_type: str | None = None
    experience: str | None = None
    requirements: list[str] | None = None
    required_skills: list[str] | None = None
    source_file_name: str | None = None
    source_file_status: str | None = None
    source_file_error: str | None = None
    created_at: datetime
    updated_at: datetime
