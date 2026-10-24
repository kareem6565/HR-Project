from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CandidateProfileExtractionRequest(BaseModel):
    resume_text: str | None = None


class WorkflowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    workflow_type: str
    status: str
    related_entity_type: str | None
    related_entity_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class AITraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_step_trace_id: UUID
    ai_component_name: str
    provider: str | None
    model_name: str | None
    prompt_version: str | None
    status: str
    latency_ms: int | None
    token_usage: dict[str, Any] | None
    input_reference: dict[str, Any] | None
    output_reference: dict[str, Any] | None
    validation_error: dict[str, Any] | None
    created_at: datetime


class JobProfileExtractionResponse(BaseModel):
    profile_id: UUID
    workflow_run_id: UUID
    version_number: int


class CandidateProfileExtractionResponse(BaseModel):
    profile_id: UUID
    workflow_run_id: UUID
    version_number: int


class CandidateEvaluationRunResponse(BaseModel):
    evaluation_id: UUID
    workflow_run_id: UUID
    version_number: int


class ScreenedCandidateResponse(BaseModel):
    candidate_id: UUID
    resume_id: UUID
    application_id: UUID
    evaluation_id: UUID
    score: str | None = None


class JobScreeningResponse(BaseModel):
    job_id: UUID
    job_title: str
    screened: list[ScreenedCandidateResponse]
