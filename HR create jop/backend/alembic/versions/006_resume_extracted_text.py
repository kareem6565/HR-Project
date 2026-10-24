"""add extracted_text to resumes

Revision ID: 006_resume_extracted_text
Revises: 005_scoring_breakdown
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_resume_extracted_text"
down_revision: str | None = "005_scoring_breakdown"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("extracted_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("resumes", "extracted_text")
