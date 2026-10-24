from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class HRDecisionCreate(BaseModel):
    decision: str
    reason: str | None = None
    candidate_evaluation_id: UUID | None = None
    expected_evaluation_id: UUID | None = None


class HRDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_application_id: UUID
    user_id: UUID
    candidate_evaluation_id: UUID | None
    decision: str
    reason: str | None
    created_at: datetime
