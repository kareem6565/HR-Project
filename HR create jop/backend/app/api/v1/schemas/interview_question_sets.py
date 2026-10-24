from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

QuestionCategory = Literal["technical", "behavioral", "situational", "candidate_specific"]


class InterviewQuestionWrite(BaseModel):
    """A curated question entry HR submits for a set (reorder/edit/add/remove)."""

    category: QuestionCategory
    text: str = Field(min_length=1, max_length=2000)
    topic: str | None = Field(default=None, max_length=250)
    requirement_key: str | None = None
    review_guide: dict[str, Any] | None = None


class InterviewQuestionSetCreate(BaseModel):
    questions: list[InterviewQuestionWrite] = Field(min_length=1)


class InterviewQuestionSetUpdate(BaseModel):
    questions: list[InterviewQuestionWrite] = Field(min_length=1)


class InterviewQuestionResponse(BaseModel):
    id: UUID | None = None
    position: int
    category: str
    text: str
    topic: str | None = None
    requirement_key: str | None = None
    review_guide: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class InterviewQuestionSetResponse(BaseModel):
    id: UUID
    organization_id: UUID
    job_application_id: UUID
    version_number: int
    status: str
    generated_by: str | None = None
    approved_by_user_id: UUID | None = None
    approved_at: datetime | None = None
    is_current: bool
    provenance: dict[str, Any] | None = None
    created_at: datetime
    questions: list[InterviewQuestionResponse]

    model_config = ConfigDict(from_attributes=True)


class InterviewQuestionSetListResponse(BaseModel):
    question_sets: list[InterviewQuestionSetResponse]
    current_id: UUID | None = None
    total: int
