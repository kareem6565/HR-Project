from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class InterviewQuestion(BaseModel):
    id: str
    text: str


class InterviewQuestionsResponse(BaseModel):
    """Question banks by category plus candidate-specific generated questions."""

    categories: list[str]
    questions: dict[str, list[InterviewQuestion]]
    candidate_id: UUID | None = None
    extra: dict[str, Any] | None = None
