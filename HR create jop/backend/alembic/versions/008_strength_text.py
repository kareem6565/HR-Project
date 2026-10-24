"""widen match_evidence.strength to text

Revision ID: 008_strength_text
Revises: 007_job_structured_fields
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_strength_text"
down_revision: str | None = "007_job_structured_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "match_evidence",
        "strength",
        existing_type=sa.String(length=50),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "match_evidence",
        "strength",
        existing_type=sa.Text(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
