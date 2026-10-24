from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CorrectionCreateRequest(BaseModel):
    correction_type: str
    job_id: UUID | None = None
    job_profile_id: UUID | None = None
    candidate_profile_id: UUID | None = None
    candidate_evaluation_id: UUID | None = None
    job_application_id: UUID | None = None
    original_ai_output: dict[str, Any] | None = None
    hr_corrected_result: dict[str, Any] | None = None
    reason: str | None = None
    evidence_reference: dict[str, Any] | None = None
    provider_info: dict[str, Any] | None = None


class CorrectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    user_id: UUID
    correction_type: str
    job_id: UUID | None = None
    job_profile_id: UUID | None = None
    candidate_profile_id: UUID | None = None
    candidate_evaluation_id: UUID | None = None
    job_application_id: UUID | None = None
    original_ai_output: dict[str, Any] | None = None
    hr_corrected_result: dict[str, Any] | None = None
    reason: str | None = None
    evidence_reference: dict[str, Any] | None = None
    provider_info: dict[str, Any] | None = None
    created_at: datetime


class FeedbackAnalyticsResponse(BaseModel):
    total_corrections: int
    corrections_by_type: dict[str, int]
    recommendation_override_rate_pct: float
    extraction_error_count: int
    requirement_match_correction_count: int


class ProposeSkillAliasRequest(BaseModel):
    alias: str
    canonical_skill: str
    reason: str | None = None


class ProposeSkillAliasResponse(BaseModel):
    canonical_skill: str
    synonyms: list[str]
    status: str


class BenchmarkCase(BaseModel):
    text: str
    term: str
    expected: bool = True


class BenchmarkRequest(BaseModel):
    test_cases: list[BenchmarkCase]


class BenchmarkResponse(BaseModel):
    total_evaluated: int
    matches: int
    accuracy_pct: float
    detailed_results: list[dict[str, Any]]
    ready_for_release: bool
