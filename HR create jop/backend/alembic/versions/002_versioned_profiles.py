"""create versioned profiles

Revision ID: 002_versioned_profiles
Revises: 001_core_recruitment_spine
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_versioned_profiles"
down_revision: str | None = "001_core_recruitment_spine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("raw_input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("profile_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'superseded')",
            name="ck_job_profiles_status",
        ),
        sa.CheckConstraint(
            "source IN ('ai_extracted', 'hr_edited', 'hr_created')",
            name="ck_job_profiles_source",
        ),
        sa.CheckConstraint(
            "status != 'approved' OR (approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_job_profiles_approved_metadata",
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "version_number", name="uq_job_profiles_job_id_version"),
    )
    op.create_index(
        "ix_job_profiles_job_id_version_number",
        "job_profiles",
        ["job_id", "version_number"],
    )
    op.create_index("ix_job_profiles_job_id_status", "job_profiles", ["job_id", "status"])
    op.create_index(
        "uq_job_profiles_current_per_job",
        "job_profiles",
        ["job_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    op.create_table(
        "candidate_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("profile_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('extracted', 'current', 'superseded', 'failed')",
            name="ck_candidate_profiles_status",
        ),
        sa.CheckConstraint(
            "source IN ('ai_extracted', 'hr_corrected', 'system_extracted')",
            name="ck_candidate_profiles_source",
        ),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resume_id", "version_number", name="uq_candidate_profiles_resume_id_version"
        ),
    )
    op.create_index(
        "ix_candidate_profiles_resume_id_version_number",
        "candidate_profiles",
        ["resume_id", "version_number"],
    )
    op.create_index(
        "ix_candidate_profiles_resume_id_status",
        "candidate_profiles",
        ["resume_id", "status"],
    )
    op.create_index(
        "uq_candidate_profiles_current_per_resume",
        "candidate_profiles",
        ["resume_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_candidate_profiles_current_per_resume", table_name="candidate_profiles")
    op.drop_index("ix_candidate_profiles_resume_id_status", table_name="candidate_profiles")
    op.drop_index("ix_candidate_profiles_resume_id_version_number", table_name="candidate_profiles")
    op.drop_table("candidate_profiles")

    op.drop_index("uq_job_profiles_current_per_job", table_name="job_profiles")
    op.drop_index("ix_job_profiles_job_id_status", table_name="job_profiles")
    op.drop_index("ix_job_profiles_job_id_version_number", table_name="job_profiles")
    op.drop_table("job_profiles")
