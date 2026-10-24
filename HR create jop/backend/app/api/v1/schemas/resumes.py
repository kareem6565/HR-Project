from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResumeCreate(BaseModel):
    file_uri: str
    original_filename: str | None = None
    content_type: str | None = None
    file_size_bytes: int | None = None


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    file_uri: str
    original_filename: str | None
    content_type: str | None
    file_size_bytes: int | None
    status: str
    created_at: datetime
    updated_at: datetime
