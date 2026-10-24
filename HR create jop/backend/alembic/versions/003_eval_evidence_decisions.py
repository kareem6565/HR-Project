"""create evaluations evidence decisions

Revision ID: 003_eval_evidence_decisions
Revises: 002_versioned_profiles
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003_eval_evidence_decisions"
down_revision: str | None = "002_versioned_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=True),
        sa.Column("recommendation", sa.String(length=50), nullable=True),
        sa.Column("explanation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("scoring_version", sa.String(length=100), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'superseded')",
            name="ck_candidate_evaluations_status",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_profile_id"], ["candidate_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["job_application_id"], ["job_applications.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["job_profile_id"], ["job_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_application_id",
            "version_number",
            name="uq_candidate_evaluations_application_id_version",
        ),
    )
    op.create_index(
        "ix_candidate_evaluations_application_id_version_number",
        "candidate_evaluations",
        ["job_application_id", "version_number"],
    )
    op.create_index(
        "ix_candidate_evaluations_application_id_status",
        "candidate_evaluations",
        ["job_application_id", "status"],
    )
    op.create_index(
        "ix_candidate_evaluations_job_profile_id",
        "candidate_evaluations",
        ["job_profile_id"],
    )
    op.create_index(
        "ix_candidate_evaluations_candidate_profile_id",
        "candidate_evaluations",
        ["candidate_profile_id"],
    )
    op.create_index(
        "uq_candidate_evaluations_current_per_application",
        "candidate_evaluations",
        ["job_application_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    op.create_table(
        "match_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("requirement_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("candidate_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("strength", sa.String(length=50), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "evidence_type IN ('matched', 'missing', 'partial')",
            name="ck_match_evidence_evidence_type",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_evaluation_id"], ["candidate_evaluations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_match_evidence_candidate_evaluation_id",
        "match_evidence",
        ["candidate_evaluation_id"],
    )
    op.create_index(
        "ix_match_evidence_candidate_evaluation_id_type",
        "match_evidence",
        ["candidate_evaluation_id", "evidence_type"],
    )

    op.create_table(
        "hr_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_evaluation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "decision IN ('advance', 'reject', 'hold')",
            name="ck_hr_decisions_decision",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_evaluation_id"], ["candidate_evaluations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["job_application_id"], ["job_applications.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hr_decisions_job_application_id_created_at",
        "hr_decisions",
        ["job_application_id", "created_at"],
    )
    op.create_index("ix_hr_decisions_user_id_created_at", "hr_decisions", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_hr_decisions_user_id_created_at", table_name="hr_decisions")
    op.drop_index("ix_hr_decisions_job_application_id_created_at", table_name="hr_decisions")
    op.drop_table("hr_decisions")

    op.drop_index("ix_match_evidence_candidate_evaluation_id_type", table_name="match_evidence")
    op.drop_index("ix_match_evidence_candidate_evaluation_id", table_name="match_evidence")
    op.drop_table("match_evidence")

    op.drop_index(
        "uq_candidate_evaluations_current_per_application",
        table_name="candidate_evaluations",
    )
    op.drop_index(
        "ix_candidate_evaluations_candidate_profile_id",
        table_name="candidate_evaluations",
    )
    op.drop_index("ix_candidate_evaluations_job_profile_id", table_name="candidate_evaluations")
    op.drop_index(
        "ix_candidate_evaluations_application_id_status",
        table_name="candidate_evaluations",
    )
    op.drop_index(
        "ix_candidate_evaluations_application_id_version_number",
        table_name="candidate_evaluations",
    )
    op.drop_table("candidate_evaluations")
