"""add score breakdown and score index

Revision ID: 005_scoring_breakdown
Revises: 004_workflow_ai_traces
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005_scoring_breakdown"
down_revision: str | None = "004_workflow_ai_traces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_evaluations",
        sa.Column("score_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_candidate_evaluations_application_id_score",
        "candidate_evaluations",
        ["job_application_id", "score"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_evaluations_application_id_score",
        table_name="candidate_evaluations",
    )
    op.drop_column("candidate_evaluations", "score_breakdown")
