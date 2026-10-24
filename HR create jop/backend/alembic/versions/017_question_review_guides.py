"""add interviewer review guides to generated questions

Revision ID: 017_question_review
Revises: 016_interview_workflow
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017_question_review"
down_revision: str | None = "016_interview_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_questions",
        sa.Column("review_guide", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interview_questions", "review_guide")
