from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InvitationCreateRequest(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=30)
    notes: str | None = None


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    job_application_id: UUID
    token: str
    expires_at: datetime
    status: str
    notes: str | None = None
    created_at: datetime


class CandidatePortalViewResponse(BaseModel):
    invitation_id: UUID
    status: str
    expires_at: datetime
    notes: str | None = None
    candidate_name: str
    job_title: str
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None


class AvailableSlotResponse(BaseModel):
    availability_id: UUID
    interviewer_id: UUID
    interviewer_name: str
    date: str
    start_time: str
    end_time: str
    duration_minutes: int
    timezone: str


class CandidateBookSlotRequest(BaseModel):
    scheduled_date: date
    scheduled_time: str = Field(min_length=1, max_length=20)
    duration_minutes: int = Field(default=60, ge=15, le=480)
    interviewer_user_id: UUID | None = None


class AvailabilityCreateRequest(BaseModel):
    interviewer_user_id: UUID
    scheduled_date: date
    start_time: str = Field(min_length=1, max_length=20)
    end_time: str = Field(min_length=1, max_length=20)
    duration_minutes: int = Field(default=60, ge=15, le=480)
    timezone: str = "UTC"


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    interviewer_user_id: UUID
    scheduled_date: date
    start_time: str
    end_time: str
    duration_minutes: int
    timezone: str
    status: str
