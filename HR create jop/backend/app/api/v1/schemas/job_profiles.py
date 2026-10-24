from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobProfileCreate(BaseModel):
    status: str
    source: str
    profile_data: dict[str, Any]
    raw_input_snapshot: dict[str, Any] | None = None


class JobProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    version_number: int
    status: str
    source: str
    profile_data: dict[str, Any]
    raw_input_snapshot: dict[str, Any] | None
    provenance: dict[str, Any] | None
    is_current: bool
    created_at: datetime
    updated_at: datetime
