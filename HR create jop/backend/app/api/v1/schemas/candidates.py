from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CandidateCreate(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None


class CandidateUpdate(BaseModel):
    email: str | None = None
    phone: str | None = None


class CandidateListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    status: str
    created_at: datetime


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    full_name: str
    email: str | None
    phone: str | None
    status: str
    created_at: datetime
    updated_at: datetime
