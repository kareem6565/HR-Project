"""add interviews table

Revision ID: 009_interviews
Revises: 008_strength_text
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "009_interviews"
down_revision: str | None = "008_strength_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "job_application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_applications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "interviewer_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("interview_type", sa.String(length=50), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("scheduled_time", sa.String(length=20), nullable=False),
        sa.Column("meeting_link", sa.String(length=500), nullable=True),
        sa.Column("feedback", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_interviews_status",
        ),
        sa.CheckConstraint(
            "interview_type IN ('technical', 'hr', 'behavioral')",
            name="ck_interviews_type",
        ),
        sa.Index("ix_interviews_organization_id_status", "organization_id", "status"),
        sa.Index("ix_interviews_job_application_id", "job_application_id"),
        sa.Index("ix_interviews_interviewer_user_id", "interviewer_user_id"),
    )


def downgrade() -> None:
    op.drop_table("interviews")
