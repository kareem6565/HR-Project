from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.workflow_step_trace import WorkflowStepTrace


class AITrace(Base):
    __tablename__ = "ai_traces"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'succeeded', 'failed', 'validation_failed', 'retried')",
            name="ck_ai_traces_status",
        ),
        Index("ix_ai_traces_workflow_step_trace_id", "workflow_step_trace_id"),
        Index("ix_ai_traces_ai_component_name_status", "ai_component_name", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_step_trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_step_traces.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_component_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_schema_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    output_schema_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_reference: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    output_reference: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    validation_error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    workflow_step_trace: Mapped[WorkflowStepTrace] = relationship(back_populates="ai_traces")
