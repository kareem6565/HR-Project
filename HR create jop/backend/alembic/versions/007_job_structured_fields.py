"""add structured job fields

Revision ID: 007_job_structured_fields
Revises: 006_resume_extracted_text
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "007_job_structured_fields"
down_revision: str | None = "006_resume_extracted_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("department", sa.String(length=100), nullable=True))
    op.add_column("jobs", sa.Column("location", sa.String(length=100), nullable=True))
    op.add_column("jobs", sa.Column("job_type", sa.String(length=50), nullable=True))
    op.add_column("jobs", sa.Column("experience", sa.String(length=100), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("required_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "required_skills")
    op.drop_column("jobs", "requirements")
    op.drop_column("jobs", "experience")
    op.drop_column("jobs", "job_type")
    op.drop_column("jobs", "location")
    op.drop_column("jobs", "department")
