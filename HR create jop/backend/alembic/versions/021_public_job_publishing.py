"""Add public job publication lifecycle."""

import sqlalchemy as sa

from alembic import op

revision = "021_public_job_publishing"
down_revision = "020_hr_ops_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("public_id", sa.String(length=32), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "publication_status", sa.String(length=20), server_default="unpublished", nullable=False
        ),
    )
    op.add_column("jobs", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("public_closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("published_job_profile_id", sa.UUID(), nullable=True))
    op.add_column("jobs", sa.Column("work_mode", sa.String(length=20), nullable=True))
    op.create_unique_constraint("uq_jobs_public_id", "jobs", ["public_id"])
    op.create_check_constraint(
        "ck_jobs_publication_status",
        "jobs",
        "publication_status IN ('unpublished', 'published', 'closed')",
    )
    op.create_check_constraint(
        "ck_jobs_work_mode",
        "jobs",
        "work_mode IS NULL OR work_mode IN ('onsite', 'hybrid', 'remote')",
    )
    op.create_foreign_key(
        "fk_jobs_published_job_profile_id_job_profiles",
        "jobs",
        "job_profiles",
        ["published_job_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_jobs_published_job_profile_id_job_profiles", "jobs", type_="foreignkey")
    op.drop_constraint("ck_jobs_work_mode", "jobs", type_="check")
    op.drop_constraint("ck_jobs_publication_status", "jobs", type_="check")
    op.drop_constraint("uq_jobs_public_id", "jobs", type_="unique")
    for name in (
        "work_mode",
        "published_job_profile_id",
        "public_closed_at",
        "published_at",
        "publication_status",
        "public_id",
    ):
        op.drop_column("jobs", name)
