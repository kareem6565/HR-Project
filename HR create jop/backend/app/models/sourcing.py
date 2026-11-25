from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SourcingSearch(Base):
    """One external candidate-sourcing request (plain-language need or job)."""

    __tablename__ = "sourcing_searches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_sourcing_searches_status",
        ),
        Index("ix_sourcing_searches_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candidates: Mapped[list[SourcingCandidate]] = relationship(
        back_populates="search", cascade="all, delete-orphan"
    )


class SourcingCandidate(Base):
    """One external profile returned by a sourcing search."""

    __tablename__ = "sourcing_candidates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('suggested', 'added_to_pipeline', 'dismissed')",
            name="ck_sourcing_candidates_status",
        ),
        Index("ix_sourcing_candidates_search", "search_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sourcing_searches.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(512), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    fit_score: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="suggested")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    search: Mapped[SourcingSearch] = relationship(back_populates="candidates")
