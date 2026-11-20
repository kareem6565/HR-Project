from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.job_application import JobApplication
    from app.models.job_profile import JobProfile
    from app.models.organization import Organization
    from app.models.screening_batch import ScreeningBatch
    from app.models.user import User


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'awaiting_profile_review', 'active', 'closed', 'archived')",
            name="ck_jobs_status",
        ),
        Index("ix_jobs_organization_id_status", "organization_id", "status"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_jobs_org_idempotency_key"),
        UniqueConstraint("public_id", name="uq_jobs_public_id"),
        CheckConstraint(
            "publication_status IN ('unpublished', 'published', 'closed')",
            name="ck_jobs_publication_status",
        ),
        CheckConstraint(
            "work_mode IS NULL OR work_mode IN ('onsite', 'hybrid', 'remote')",
            name="ck_jobs_work_mode",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    public_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=lambda: secrets.token_urlsafe(24)
    )
    publication_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unpublished", server_default="unpublished"
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    public_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_job_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "job_profiles.id",
            ondelete="SET NULL",
            name="fk_jobs_published_job_profile_id_job_profiles",
            use_alter=True,
        ),
        nullable=True,
    )
    work_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requirements: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    required_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_file_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_file_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_file_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_file_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="jobs")
    created_by: Mapped[User | None] = relationship(back_populates="created_jobs")
    applications: Mapped[list[JobApplication]] = relationship(back_populates="job")
    profiles: Mapped[list[JobProfile]] = relationship(
        back_populates="job", foreign_keys="JobProfile.job_id"
    )
    screening_batches: Mapped[list[ScreeningBatch]] = relationship(back_populates="job")
