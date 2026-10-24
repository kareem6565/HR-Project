from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.candidate_evaluation import CandidateEvaluation
    from app.models.hr_decision import HRDecision
    from app.models.interview import Interview
    from app.models.interview_question_set import InterviewQuestionSet
    from app.models.job import Job
    from app.models.organization import Organization
    from app.models.resume import Resume


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'created', 'analysis_pending', 'analyzing', 'analysis_failed', "
            "'ready_for_review', 'hold', 'advanced', 'rejected', 'archived'"
            ")",
            name="ck_job_applications_status",
        ),
        Index("ix_job_applications_organization_id_status", "organization_id", "status"),
        Index("ix_job_applications_job_id_status", "job_id", "status"),
        Index("ix_job_applications_candidate_id", "candidate_id"),
        Index("ix_job_applications_resume_id", "resume_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="RESTRICT"), nullable=False
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization] = relationship()
    job: Mapped[Job] = relationship(back_populates="applications")
    candidate: Mapped[Candidate] = relationship(back_populates="applications")
    resume: Mapped[Resume] = relationship(back_populates="applications")
    evaluations: Mapped[list[CandidateEvaluation]] = relationship(back_populates="job_application")
    hr_decisions: Mapped[list[HRDecision]] = relationship(back_populates="job_application")
    interviews: Mapped[list[Interview]] = relationship(back_populates="job_application")
    question_sets: Mapped[list[InterviewQuestionSet]] = relationship(
        back_populates="job_application"
    )
