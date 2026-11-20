"""Add manually managed job distribution campaigns and anonymous visit events."""

import sqlalchemy as sa

from alembic import op

revision = "025_job_distributions"
down_revision = "024_linkedin_job_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_distributions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("approved_profile_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("campaign_name", sa.String(length=120), nullable=False),
        sa.Column("tracking_key", sa.String(length=32), nullable=False),
        sa.Column("post_text", sa.Text(), server_default="", nullable=False),
        sa.Column("ai_generated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("external_post_url", sa.String(length=1000), nullable=True),
        sa.Column("hr_reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("hr_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "channel IN ('linkedin', 'facebook', 'wuzzuf', 'other')",
            name="ck_job_distributions_channel",
        ),
        sa.CheckConstraint("status IN ('draft', 'shared')", name="ck_job_distributions_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_profile_id"], ["job_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["hr_reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tracking_key", name="uq_job_distributions_tracking_key"),
    )
    op.create_index(
        "ix_job_distributions_org_job", "job_distributions", ["organization_id", "job_id"]
    )
    op.create_table(
        "job_distribution_views",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("distribution_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["distribution_id"], ["job_distributions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_distribution_views_distribution_created",
        "job_distribution_views",
        ["distribution_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_distribution_views_distribution_created", table_name="job_distribution_views")
    op.drop_table("job_distribution_views")
    op.drop_index("ix_job_distributions_org_job", table_name="job_distributions")
    op.drop_table("job_distributions")
