from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.interview_question import InterviewQuestion
    from app.models.job_application import JobApplication
    from app.models.organization import Organization
    from app.models.user import User


class InterviewQuestionSet(Base):
    """A versioned, curator-approved set of interview questions for an application.

    Lifecycle: a generated set starts in ``generated`` (AI draft), HR can edit it
    (select / edit / reorder / add / remove without replacing the row), and
    approving it moves the set to ``approved`` and records the approving user and
    timestamp. Regeneration never overwrites an approved set; it always creates a
    new version so audit history is preserved.
    """

    __tablename__ = "interview_question_sets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('generated', 'approved', 'superseded')",
            name="ck_interview_question_sets_status",
        ),
        Index("ix_question_sets_application_version", "job_application_id", "version_number"),
        Index("ix_question_sets_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    job_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generated")
    generated_by: Mapped[str] = mapped_column(String(50), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped[Organization] = relationship()
    job_application: Mapped[JobApplication] = relationship(back_populates="question_sets")
    approving_user: Mapped[User | None] = relationship()
    questions: Mapped[list[InterviewQuestion]] = relationship(
        back_populates="question_set",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.position",
    )
