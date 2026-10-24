from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.interview_question_set import InterviewQuestionSet


class InterviewQuestion(Base):
    """A single curated interview question within a question set.

    ``position`` controls display order (HR can reorder). ``topic`` is a
    readable subject label (e.g. a job requirement text or a skill). When a
    question targets a specific job requirement, ``requirement_key`` references
    the exact requirement key the AI was supplied, so the question stays
    traceable to the approved JobProfile.
    """

    __tablename__ = "interview_questions"
    __table_args__ = (
        Index("ix_questions_set_position", "question_set_id", "position"),
        Index("ix_questions_requirement_key", "requirement_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_question_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str | None] = mapped_column(String(250), nullable=True)
    requirement_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_guide: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    question_set: Mapped[InterviewQuestionSet] = relationship(back_populates="questions")
