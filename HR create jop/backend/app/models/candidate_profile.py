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
    from app.models.resume import Resume


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('extracted', 'current', 'superseded', 'failed')",
            name="ck_candidate_profiles_status",
        ),
        CheckConstraint(
            "source IN ('ai_extracted', 'hr_corrected', 'system_extracted')",
            name="ck_candidate_profiles_source",
        ),
        UniqueConstraint(
            "resume_id", "version_number", name="uq_candidate_profiles_resume_id_version"
        ),
        Index("ix_candidate_profiles_resume_id_version_number", "resume_id", "version_number"),
        Index("ix_candidate_profiles_resume_id_status", "resume_id", "status"),
        Index(
            "uq_candidate_profiles_current_per_resume",
            "resume_id",
            unique=True,
            postgresql_where=text("is_current = true"),
            sqlite_where=text("is_current = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="RESTRICT"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    profile_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    resume: Mapped[Resume] = relationship(back_populates="profiles")
    evaluations: Mapped[list[CandidateEvaluation]] = relationship(
        back_populates="candidate_profile"
    )
