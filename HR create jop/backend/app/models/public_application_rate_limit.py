from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PublicApplicationRateLimit(Base):
    __tablename__ = "public_application_rate_limits"
    __table_args__ = (Index("ix_public_application_rate_limits_window", "window_started_at"),)

    fingerprint_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submission_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
