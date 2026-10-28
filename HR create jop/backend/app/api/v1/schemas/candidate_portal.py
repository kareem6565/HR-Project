from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InvitationCreateRequest(BaseModel):
    expires_in_days: Literal[7] = 7
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
    status: str
    expires_at: datetime
    candidate_name: str
    job_title: str
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    scheduled_date: str | None = None
    scheduled_time: str | None = None
    scheduled_duration_minutes: int | None = None
    timezone: str | None = None


class AvailableSlotResponse(BaseModel):
    availability_id: UUID
    interviewer_name: str
    date: str
    start_time: str
    end_time: str
    duration_minutes: int
    timezone: str


class CandidateBookSlotRequest(BaseModel):
    token: str = Field(min_length=32, max_length=64)
    availability_id: UUID
    scheduled_time: str = Field(min_length=1, max_length=20)


class CandidatePortalTokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=64)


class CandidatePortalMonthSlotsRequest(CandidatePortalTokenRequest):
    month: date

    @field_validator("month")
    @classmethod
    def validate_month_start(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("month must be the first day of a calendar month")
        return value


class CandidateBookingResponse(BaseModel):
    status: str
    scheduled_date: str
    scheduled_time: str
    scheduled_duration_minutes: int
    timezone: str


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
