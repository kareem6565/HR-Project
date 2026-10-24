from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.candidate_evaluation import CandidateEvaluation


class MatchEvidence(Base):
    __tablename__ = "match_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('matched', 'missing', 'partial')",
            name="ck_match_evidence_evidence_type",
        ),
        Index("ix_match_evidence_candidate_evaluation_id", "candidate_evaluation_id"),
        Index(
            "ix_match_evidence_candidate_evaluation_id_type",
            "candidate_evaluation_id",
            "evidence_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_evaluations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    requirement_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    candidate_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    strength: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    candidate_evaluation: Mapped[CandidateEvaluation] = relationship(
        back_populates="evidence_items"
    )
