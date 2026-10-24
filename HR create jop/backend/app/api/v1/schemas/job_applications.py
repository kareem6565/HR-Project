from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobApplicationCreate(BaseModel):
    job_id: UUID
    candidate_id: UUID
    resume_id: UUID


class JobApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    job_id: UUID
    candidate_id: UUID
    resume_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime


class RequirementEvidenceSummary(BaseModel):
    """Compact per-requirement evidence item inside an application summary.

    Mirrors the persisted assertion of one MatchEvidence row against the
    current evaluation; ``text`` is the human-readable requirement label for
    display. The frontend never recomputes or classifies these values.
    """

    requirement_key: str | None = None
    evidence_type: str
    text: str = ""


class ApplicationSummaryResponse(BaseModel):
    """Organization-wide application list row used by ApplicationsList and
    Matching Results.

    Composed read model (application + candidate + job + current evaluation
    score). ``score`` is returned as a string to match the existing evaluation
    response convention. ``group`` is the backend-assigned deterministic
    grouping band for the current evaluation; ``evidence`` is the compact
    requirement-level evidence summary of the current evaluation (matched /
    partial / missing), so ranked list views can show real data without an
    N+1 of per-application calls.
    """

    id: UUID
    candidate_id: UUID
    candidate_name: str
    job_id: UUID
    job_title: str
    score: str | None = None
    group: str | None = None
    status: str
    created_at: datetime
    evidence: list[RequirementEvidenceSummary] = Field(default_factory=list)
