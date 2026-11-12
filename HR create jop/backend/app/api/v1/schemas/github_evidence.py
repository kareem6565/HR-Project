from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class GitHubEvidenceRequest(BaseModel):
    repository_urls: list[str] = Field(default_factory=list, max_length=5)


class GitHubEvidenceStartResponse(BaseModel):
    analysis_id: UUID
    status: str
    consent_url: str
    consent_link_expires_at: datetime


class GitHubEvidencePreviewRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class GitHubEvidencePreviewResponse(BaseModel):
    organization_name: str
    consent_text: str
    consent_version: str
    repository_urls: list[HttpUrl]
    link_expires_at: datetime


class GitHubEvidenceDecisionRequest(GitHubEvidencePreviewRequest):
    decision: Literal["accepted", "declined"]
    self_attested: Literal[True]


class GitHubEvidenceObservation(BaseModel):
    evidence_id: str
    kind: str
    source_url: HttpUrl
    content: dict
    limitation: str


class GitHubRequirementAssessmentResponse(BaseModel):
    requirement_key: str
    requirement_text: str
    requirement_category: str
    classification: Literal["direct", "indirect", "insufficient"]
    evidence_ids: list[str]
    explanation: str
    limitations: list[str]


class GitHubEvidenceAnalysisResponse(BaseModel):
    id: UUID
    status: Literal[
        "awaiting_consent",
        "pending",
        "in_progress",
        "completed",
        "failed",
        "declined",
        "consent_expired",
    ]
    repository_urls: list[str]
    evidence: list[GitHubEvidenceObservation] = Field(default_factory=list)
    assessments: list[GitHubRequirementAssessmentResponse] = Field(default_factory=list)
    error_code: str | None = None
    attempts: int
    consent_responded_at: datetime | None = None
    consent_link_expires_at: datetime | None = None
    retry_after_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
