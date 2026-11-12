"""Track organization-scoped LinkedIn job imports from Apify."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "024_linkedin_job_imports"
down_revision = "023_public_application_screening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "linkedin_job_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("source_job_id", sa.String(length=64), nullable=True),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("actor_run_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_code", sa.String(length=48), nullable=True),
        sa.Column("result_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_linkedin_job_imports_status",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "source_url", name="uq_linkedin_import_org_url"),
        sa.UniqueConstraint("organization_id", "source_job_id", name="uq_linkedin_import_org_job"),
    )
    op.create_index(
        "ix_linkedin_job_imports_org_status",
        "linkedin_job_imports",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_linkedin_job_imports_org_status", table_name="linkedin_job_imports")
    op.drop_table("linkedin_job_imports")
