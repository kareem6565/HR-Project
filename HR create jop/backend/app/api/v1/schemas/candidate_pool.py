from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class JobCandidateSummary(BaseModel):
    """A candidate within a job's application pool, with ranking context.

    Composed read model returned by the job-scoped candidate ranking endpoint.
    Never includes extracted text. ``score`` is returned as a string to match
    the existing evaluation response convention.
    """

    candidate_id: UUID
    application_id: UUID
    full_name: str
    email: str | None = None
    phone: str | None = None
    status: str
    score: str | None = None
    group: str
    decision: str | None = None
    decision_created_at: datetime | None = None


class TalentPoolRowResponse(BaseModel):
    """One hold/advanced candidate in the organization-wide talent pool.

    Superset of ``JobCandidateSummary``: adds job context (``job_id``,
    ``job_title``) so a consumer like the talent pool page can display which
    job a hold/advanced candidate is linked to.
    """

    candidate_id: UUID
    application_id: UUID
    job_id: UUID
    job_title: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    status: str
    score: str | None = None
    group: str
    skills: list[str] = Field(default_factory=list)
    decision: str | None = None
    decision_created_at: datetime | None = None
