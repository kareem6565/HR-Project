from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.workflow_step_trace import WorkflowStepTrace


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'pending', 'running', 'waiting_for_human', 'completed', 'failed', 'cancelled'"
            ")",
            name="ck_workflow_runs_status",
        ),
        CheckConstraint(
            "related_entity_type IS NULL OR related_entity_type IN ("
            "'job', 'candidate', 'resume', 'job_application', 'job_profile', "
            "'candidate_profile', 'candidate_evaluation', 'chat_thread'"
            ")",
            name="ck_workflow_runs_related_entity_type",
        ),
        Index("ix_workflow_runs_organization_id_status", "organization_id", "status"),
        Index("ix_workflow_runs_workflow_type_status", "workflow_type", "status"),
        Index(
            "ix_workflow_runs_related_entity_type_id",
            "related_entity_type",
            "related_entity_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped[Organization] = relationship(back_populates="workflow_runs")
    step_traces: Mapped[list[WorkflowStepTrace]] = relationship(
        back_populates="workflow_run",
        passive_deletes=True,
    )
