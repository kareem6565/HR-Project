from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.candidate_profile import CandidateProfile
    from app.models.hr_decision import HRDecision
    from app.models.job_application import JobApplication
    from app.models.job_profile import JobProfile
    from app.models.match_evidence import MatchEvidence


class CandidateEvaluation(Base):
    __tablename__ = "candidate_evaluations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'superseded')",
            name="ck_candidate_evaluations_status",
        ),
        UniqueConstraint(
            "job_application_id",
            "version_number",
            name="uq_candidate_evaluations_application_id_version",
        ),
        Index(
            "ix_candidate_evaluations_application_id_version_number",
            "job_application_id",
            "version_number",
        ),
        Index("ix_candidate_evaluations_application_id_status", "job_application_id", "status"),
        Index("ix_candidate_evaluations_job_profile_id", "job_profile_id"),
        Index("ix_candidate_evaluations_candidate_profile_id", "candidate_profile_id"),
        Index(
            "ix_candidate_evaluations_application_id_score",
            "job_application_id",
            "score",
        ),
        Index(
            "uq_candidate_evaluations_current_per_application",
            "job_application_id",
            unique=True,
            postgresql_where=text("is_current = true"),
            sqlite_where=text("is_current = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_applications.id", ondelete="RESTRICT"), nullable=False
    )
    job_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    scoring_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_engine_version: Mapped[str | None] = mapped_column(String(50), nullable=True, default="2.0")
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job_application: Mapped[JobApplication] = relationship(back_populates="evaluations")
    job_profile: Mapped[JobProfile] = relationship(back_populates="evaluations")
    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="evaluations")
    evidence_items: Mapped[list[MatchEvidence]] = relationship(
        back_populates="candidate_evaluation"
    )
    hr_decisions: Mapped[list[HRDecision]] = relationship(back_populates="candidate_evaluation")
