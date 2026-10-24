"""add chat threads and messages

Revision ID: 011_chat
Revises: 010_interview_questions
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "011_chat"
down_revision: str | None = "010_interview_questions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
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
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_chat_threads_status"),
        sa.Index("ix_chat_threads_org_updated", "organization_id", "updated_at"),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("position", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "chat_thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
        sa.Column("tool_results", postgresql.JSONB(), nullable=True),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role"),
        sa.Index("ix_chat_messages_thread_position", "chat_thread_id", "position"),
    )
    op.drop_constraint("ck_workflow_runs_related_entity_type", "workflow_runs", type_="check")
    op.create_check_constraint(
        "ck_workflow_runs_related_entity_type",
        "workflow_runs",
        "related_entity_type IS NULL OR related_entity_type IN ("
        "'job', 'candidate', 'resume', 'job_application', 'job_profile', "
        "'candidate_profile', 'candidate_evaluation', 'chat_thread'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_workflow_runs_related_entity_type", "workflow_runs", type_="check")
    op.create_check_constraint(
        "ck_workflow_runs_related_entity_type",
        "workflow_runs",
        "related_entity_type IS NULL OR related_entity_type IN ("
        "'job', 'candidate', 'resume', 'job_application', 'job_profile', "
        "'candidate_profile', 'candidate_evaluation'"
        ")",
    )
    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
