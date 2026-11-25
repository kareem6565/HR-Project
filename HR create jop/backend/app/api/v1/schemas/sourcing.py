from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SourcingSearchRequest(BaseModel):
    job_id: UUID | None = None
    query_text: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_query_or_job(self):
        if not self.query_text.strip() and self.job_id is None:
            raise ValueError("Describe who you need, or pick a job to source for.")
        return self


class SourcingCandidateOut(BaseModel):
    id: UUID
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    profile_url: str | None = None
    email: str | None = None
    phone: str | None = None
    fit_score: int | None = None
    status: Literal["suggested", "added_to_pipeline", "dismissed"]


class SourcingSearchResponse(BaseModel):
    id: UUID
    job_id: UUID | None = None
    query_text: str
    provider: str
    status: Literal["queued", "running", "succeeded", "failed"]
    error_code: str | None = None
    error_message: str | None = None
    candidates: list[SourcingCandidateOut] = []
    created_at: datetime
    updated_at: datetime
