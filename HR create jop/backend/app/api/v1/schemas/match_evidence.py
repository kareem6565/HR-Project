from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MatchEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_evaluation_id: UUID
    evidence_type: str
    requirement_ref: dict[str, Any] | None
    candidate_evidence: dict[str, Any] | None
    strength: str | None
    provenance: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
