from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class LinkedInJobImportRequest(BaseModel):
    source_url: AnyHttpUrl


class LinkedInJobImportResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id: str = Field(alias="jobId", max_length=64)
    job_url: AnyHttpUrl = Field(alias="jobUrl")
    title: str = Field(min_length=1, max_length=255)
    company_name: str | None = Field(default=None, alias="companyName", max_length=255)
    location: str | None = Field(default=None, max_length=255)
    description: str = Field(min_length=1, max_length=50_000)
    employment_type: str | None = Field(default=None, alias="employmentType", max_length=100)
    seniority_level: str | None = Field(default=None, alias="seniorityLevel", max_length=100)
    workplace_type: str | None = Field(default=None, alias="workplaceType", max_length=100)
    description_html: str | None = Field(default=None, alias="descriptionHtml", max_length=50_000)
    posted_at: str | None = Field(default=None, alias="postedAt", max_length=100)

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_required_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class LinkedInJobImportResponse(BaseModel):
    id: UUID
    source_url: str
    status: Literal["queued", "running", "succeeded", "failed"]
    error_code: str | None = None
    error_message: str | None = None
    result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
