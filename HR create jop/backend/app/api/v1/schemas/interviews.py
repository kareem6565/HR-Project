from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

InterviewStatus = Literal["scheduled", "completed", "cancelled"]
InterviewType = Literal["technical", "hr", "behavioral"]


class InterviewerResponse(BaseModel):
    """An org user eligible to run interviews."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str


class InterviewCreate(BaseModel):
    """Schedule an interview for a candidate against a job.

    The backend resolves the applicant's JobApplication for the given
    candidate/job pair — an interview only makes sense for someone who has
    actually applied and been screened.
    """

    candidate_id: UUID
    job_id: UUID
    interviewer_user_id: UUID | None = None
    interview_type: InterviewType = "technical"
    scheduled_date: date
    scheduled_time: str = Field(min_length=1, max_length=20)
    scheduled_duration_minutes: int = Field(default=60, ge=15, le=480)
    meeting_link: str | None = None
    interview_question_set_id: UUID | None = None


class InterviewCancel(BaseModel):
    status: Literal["cancelled"]


class InterviewFeedbackCreate(BaseModel):
    """Interviewer feedback; marks the interview as completed."""

    technical: int = Field(ge=1, le=5)
    communication: int = Field(ge=1, le=5)
    problem_solving: int = Field(ge=1, le=5)
    overall: float = Field(ge=1, le=5)
    comments: str | None = None
    submitted_by: str | None = None


class InterviewResponse(BaseModel):
    """Composed interview read model with candidate/job/interviewer labels.

    Status and type are returned lowercase to match the backend's convention;
    the frontend service maps them to display form.
    """

    id: UUID
    organization_id: UUID
    job_application_id: UUID
    interviewer_user_id: UUID | None
    interviewer_name: str | None
    candidate_id: UUID
    candidate_name: str
    candidate_email: str | None = None
    job_id: UUID
    job_title: str
    interview_type: str
    status: str
    scheduled_date: date
    scheduled_time: str
    scheduled_duration_minutes: int | None = None
    meeting_link: str | None = None
    interview_question_set_id: UUID | None = None
    feedback: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewListResponse(BaseModel):
    interviews: list[InterviewResponse]
    total: int
