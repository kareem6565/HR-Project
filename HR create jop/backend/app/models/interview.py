from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.job_application import JobApplication
    from app.models.organization import Organization
    from app.models.user import User


class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_interviews_status",
        ),
        CheckConstraint(
            "interview_type IN ('technical', 'hr', 'behavioral')",
            name="ck_interviews_type",
        ),
        Index("ix_interviews_organization_id_status", "organization_id", "status"),
        Index("ix_interviews_job_application_id", "job_application_id"),
        Index("ix_interviews_interviewer_user_id", "interviewer_user_id"),
        Index("ix_interviews_scheduled_start_at", "scheduled_start_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    job_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_applications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    interviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    interview_question_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_question_sets.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="scheduled")
    interview_type: Mapped[str] = mapped_column(String(50), nullable=False, default="technical")
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_time: Mapped[str] = mapped_column(String(20), nullable=False)
    scheduled_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    # Nullable for legacy rows: migration 021 must not invent/backfill historical instants.
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meeting_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    google_calendar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calendar_sync_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_required")
    calendar_sync_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped[Organization] = relationship()
    job_application: Mapped[JobApplication] = relationship(back_populates="interviews")
    interviewer: Mapped[User | None] = relationship()
