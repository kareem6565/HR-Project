from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TalentPoolConsent(Base):
    """One candidate's one-time consent link and its recorded response/grant."""

    __tablename__ = "talent_pool_consents"
    __table_args__ = (
        CheckConstraint(
            "response IS NULL OR response IN ('accepted', 'declined')",
            name="ck_talent_pool_consents_response",
        ),
        UniqueConstraint("token_hash", name="uq_talent_pool_consents_token_hash"),
        Index("ix_talent_pool_consents_candidate_org", "candidate_id", "organization_id"),
        Index("ix_talent_pool_consents_org_expiry", "organization_id", "consent_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    link_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    link_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response: Mapped[str | None] = mapped_column(String(20), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
