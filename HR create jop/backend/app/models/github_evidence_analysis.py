from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GitHubEvidenceAnalysis(Base):
    """One consent-bound GitHub evidence collection and review for an application."""

    __tablename__ = "github_evidence_analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'awaiting_consent', 'pending', 'in_progress', 'completed', 'failed', 'declined', "
            "'consent_expired')",
            name="ck_github_evidence_analyses_status",
        ),
        CheckConstraint(
            "attempts >= 0 AND attempts <= 3", name="ck_github_evidence_analyses_attempts"
        ),
        CheckConstraint(
            "consent_response IS NULL OR consent_response IN ('accepted', 'declined')",
            name="ck_github_evidence_analyses_consent_response",
        ),
        Index("ix_github_evidence_analyses_org_application", "organization_id", "application_id"),
        Index("ix_github_evidence_analyses_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False
    )
    job_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="awaiting_consent")
    repository_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    consent_link_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_link_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_response: Mapped[str | None] = mapped_column(String(20))
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)
    consent_version: Mapped[str] = mapped_column(String(40), nullable=False)
    consent_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    assessments: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_after_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
