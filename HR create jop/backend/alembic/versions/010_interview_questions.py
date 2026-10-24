"""add interview question sets and questions

Revision ID: 010_interview_questions
Revises: 009_interviews
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "010_interview_questions"
down_revision: str | None = "009_interviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interviews",
        sa.Column(
            "scheduled_duration_minutes",
            sa.Integer(),
            server_default="60",
            nullable=False,
        ),
    )
    op.create_table(
        "interview_question_sets",
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
            sa.ForeignKey("job_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("generated_by", sa.String(length=50), nullable=True),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance", postgresql.JSONB(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
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
            "status IN ('generated', 'approved', 'superseded')",
            name="ck_interview_question_sets_status",
        ),
        sa.Index("ix_question_sets_application_version", "job_application_id", "version_number"),
        sa.Index("ix_question_sets_org", "organization_id"),
    )
    op.create_table(
        "interview_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "question_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_question_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=250), nullable=True),
        sa.Column("requirement_key", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Index("ix_questions_set_position", "question_set_id", "position"),
        sa.Index("ix_questions_requirement_key", "requirement_key"),
    )
    op.add_column(
        "interviews",
        sa.Column(
            "interview_question_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_question_sets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("interviews", "interview_question_set_id")
    op.drop_table("interview_questions")
    op.drop_table("interview_question_sets")
    op.drop_column("interviews", "scheduled_duration_minutes")
