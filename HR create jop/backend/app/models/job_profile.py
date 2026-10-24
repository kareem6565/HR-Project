from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.candidate_evaluation import CandidateEvaluation
    from app.models.job import Job
    from app.models.user import User


class JobProfile(Base):
    __tablename__ = "job_profiles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'approved', 'superseded')",
            name="ck_job_profiles_status",
        ),
        CheckConstraint(
            "source IN ('ai_extracted', 'hr_edited', 'hr_created')",
            name="ck_job_profiles_source",
        ),
        CheckConstraint(
            "status != 'approved' OR (approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_job_profiles_approved_metadata",
        ),
        UniqueConstraint("job_id", "version_number", name="uq_job_profiles_job_id_version"),
        Index("ix_job_profiles_job_id_version_number", "job_id", "version_number"),
        Index("ix_job_profiles_job_id_status", "job_id", "status"),
        Index(
            "uq_job_profiles_current_per_job",
            "job_id",
            unique=True,
            postgresql_where=text("is_current = true"),
            sqlite_where=text("is_current = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_input_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    profile_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    job: Mapped[Job] = relationship(back_populates="profiles")
    approved_by: Mapped[User | None] = relationship(back_populates="approved_job_profiles")
    evaluations: Mapped[list[CandidateEvaluation]] = relationship(back_populates="job_profile")
