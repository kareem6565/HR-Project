from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.candidate_evaluation import CandidateEvaluation
    from app.models.job_application import JobApplication
    from app.models.user import User


class HRDecision(Base):
    __tablename__ = "hr_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('advance', 'reject', 'hold')",
            name="ck_hr_decisions_decision",
        ),
        Index("ix_hr_decisions_job_application_id_created_at", "job_application_id", "created_at"),
        Index("ix_hr_decisions_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_applications.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_evaluations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    job_application: Mapped[JobApplication] = relationship(back_populates="hr_decisions")
    user: Mapped[User] = relationship(back_populates="hr_decisions")
    candidate_evaluation: Mapped[CandidateEvaluation | None] = relationship(
        back_populates="hr_decisions"
    )
