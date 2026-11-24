from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

PipelineStage = Literal[
    "screening",
    "review",
    "interview",
    "offer",
    "hired",
    "rejected",
    "withdrawn",
    "archived",
]


class PipelineTransitionRequest(BaseModel):
    idempotency_key: UUID
    expected_stage: PipelineStage
    to_stage: PipelineStage
    reason_code: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("reason_code")
    @classmethod
    def normalize_reason_code(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class PipelineCorrectionRequest(BaseModel):
    idempotency_key: UUID
    expected_stage: Literal["hired"]
    to_stage: Literal["screening", "review", "interview", "offer", "withdrawn"]
    reason_code: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason_code", "reason")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field must not be blank.")
        return normalized


class PipelineTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    job_application_id: UUID
    actor_user_id: UUID | None
    from_stage: str | None
    to_stage: str
    reason_code: str | None
    source: str
    created_at: datetime


class PipelineStateResponse(BaseModel):
    application_id: UUID
    status: str
    pipeline_stage: PipelineStage
    allowed_next_stages: list[PipelineStage]
    allowed_correction_stages: list[PipelineStage]
    reason_required_stages: list[PipelineStage]
    is_admin: bool
    transitions: list[PipelineTransitionResponse]
    replayed: bool = False
