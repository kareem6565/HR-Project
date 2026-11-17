from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AIUsageEvent(Base):
    """Minimal, payload-free record of one outbound model attempt."""

    __tablename__ = "ai_usage_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'succeeded', 'failed', 'cost_alert')",
            name="ck_ai_usage_events_status",
        ),
        CheckConstraint(
            "reported_cost_usd IS NULL OR reported_cost_usd >= 0", name="ck_ai_usage_events_cost"
        ),
        Index("ix_ai_usage_events_created_at", "created_at"),
        Index("ix_ai_usage_events_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL")
    )
    feature: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="started")
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_category: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(128))
    provider_request_id: Mapped[str | None] = mapped_column(String(160))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    reported_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIUsageCounter(Base):
    """Atomic UTC minute/day counters, shared across all backend workers."""

    __tablename__ = "ai_usage_counters"

    bucket_key: Mapped[str] = mapped_column(String(180), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AIPolicyControl(Base):
    """Persistent global circuit breaker for unexpected non-zero free-model cost."""

    __tablename__ = "ai_policy_controls"

    control_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
