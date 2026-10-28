from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.interview import Interview
    from app.models.interview_availability import InterviewAvailability
    from app.models.job_application import JobApplication
    from app.models.organization import Organization


class CandidateInvitation(Base):
    __tablename__ = "candidate_invitations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'booked', 'expired', 'cancelled')",
            name="ck_candidate_invitations_status",
        ),
        Index("ix_candidate_invitations_token_hash", "token_hash", unique=True),
        Index("ix_candidate_invitations_app", "job_application_id"),
        Index("ix_candidate_invitations_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    job_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    booked_interview_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="SET NULL"), nullable=True
    )
    booked_availability_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_availabilities.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped[Organization] = relationship()
    job_application: Mapped[JobApplication] = relationship()
    booked_interview: Mapped[Interview | None] = relationship(foreign_keys=[booked_interview_id])
    booked_availability: Mapped[InterviewAvailability | None] = relationship(
        foreign_keys=[booked_availability_id]
    )
