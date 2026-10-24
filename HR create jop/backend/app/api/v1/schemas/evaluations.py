from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class CandidateEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("score", mode="before")
    @classmethod
    def _stringify_score(cls, value: object) -> str | None:
        """Stringify the numeric score column (Decimal) for the response contract."""
        if value is None:
            return None
        return str(value)

    id: UUID
    job_application_id: UUID
    job_profile_id: UUID
    candidate_profile_id: UUID
    version_number: int
    status: str
    score: str | None
    recommendation: str | None
    explanation: dict[str, Any] | None
    score_breakdown: dict[str, Any] | None
    scoring_version: str | None
    provenance: dict[str, Any] | None
    is_current: bool
    created_at: datetime
    updated_at: datetime
