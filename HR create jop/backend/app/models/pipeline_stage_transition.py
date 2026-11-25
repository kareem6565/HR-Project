from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.job_application import JobApplication
    from app.models.organization import Organization
    from app.models.user import User


class PipelineStageTransition(Base):
    """Append-only, organization-scoped record of a human pipeline stage change."""

    __tablename__ = "pipeline_stage_transitions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "job_application_id",
            "actor_user_id",
            "idempotency_key",
            name="uq_pipeline_stage_transitions_idempotency",
        ),
        Index(
            "ix_pipeline_stage_transitions_org_application_created",
            "organization_id",
            "job_application_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    job_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_applications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    from_stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # HR notes may contain sensitive details. They are never returned in list/history APIs.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    organization: Mapped[Organization] = relationship()
    job_application: Mapped[JobApplication] = relationship(back_populates="pipeline_transitions")
    actor: Mapped[User | None] = relationship()
