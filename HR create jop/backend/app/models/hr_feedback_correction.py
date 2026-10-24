from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class HRFeedbackCorrection(Base):
    __tablename__ = "hr_feedback_corrections"
    __table_args__ = (
        CheckConstraint(
            "correction_type IN ("
            "'extraction_correction', "
            "'skill_alias_correction', "
            "'requirement_match_correction', "
            "'scoring_rule_correction', "
            "'recommendation_override', "
            "'final_decision', "
            "'interview_feedback_correction', "
            "'post_interview_decision'"
            ")",
            name="ck_hr_feedback_corrections_type",
        ),
        Index("ix_hr_feedback_org_type", "organization_id", "correction_type"),
        Index("ix_hr_feedback_eval", "candidate_evaluation_id"),
        Index("ix_hr_feedback_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    correction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    job_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_profiles.id", ondelete="SET NULL"), nullable=True
    )
    candidate_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="SET NULL"), nullable=True
    )
    candidate_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_evaluations.id", ondelete="SET NULL"), nullable=True
    )
    job_application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_applications.id", ondelete="SET NULL"), nullable=True
    )
    original_ai_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    hr_corrected_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_reference: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    provider_info: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    organization: Mapped[Organization] = relationship()
    user: Mapped[User] = relationship()
