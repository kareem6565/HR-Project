"""Add consent-bound public GitHub evidence analyses."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "026_github_evidence"
down_revision = "025_job_distributions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_evidence_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("job_profile_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("repository_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("consent_link_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_link_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_response", sa.String(length=20), nullable=True),
        sa.Column("consent_text", sa.Text(), nullable=False),
        sa.Column("consent_version", sa.String(length=40), nullable=False),
        sa.Column("consent_responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("assessments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_after_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ("
            "'awaiting_consent', 'pending', 'in_progress', 'completed', 'failed', 'declined', "
            "'consent_expired')",
            name="ck_github_evidence_analyses_status",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= 3", name="ck_github_evidence_analyses_attempts"
        ),
        sa.CheckConstraint(
            "consent_response IS NULL OR consent_response IN ('accepted', 'declined')",
            name="ck_github_evidence_analyses_consent_response",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_profile_id"], ["job_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_github_evidence_analyses_token_hash"),
    )
    op.create_index(
        "ix_github_evidence_analyses_org_application",
        "github_evidence_analyses",
        ["organization_id", "application_id"],
    )
    op.create_index(
        "ix_github_evidence_analyses_status_created",
        "github_evidence_analyses",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_github_evidence_analyses_status_created", table_name="github_evidence_analyses"
    )
    op.drop_index(
        "ix_github_evidence_analyses_org_application", table_name="github_evidence_analyses"
    )
    op.drop_table("github_evidence_analyses")
