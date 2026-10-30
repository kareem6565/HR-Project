"""retain job description source files and deduplicate vacancy creates

Revision ID: 019_job_vacancy_files
Revises: 018_dual_workspace_roles
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "019_job_vacancy_files"
down_revision: str | None = "018_dual_workspace_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("description_text", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("jobs", sa.Column("source_file_uri", sa.String(length=512), nullable=True))
    op.add_column("jobs", sa.Column("source_file_name", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("source_file_text", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("source_file_sha256", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("source_file_status", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("source_file_error", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_jobs_org_idempotency_key", "jobs", ["organization_id", "idempotency_key"]
    )
    op.add_column("job_profiles", sa.Column("request_key", sa.String(length=128), nullable=True))
    op.create_unique_constraint(
        "uq_job_profiles_job_request_key", "job_profiles", ["job_id", "request_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_job_profiles_job_request_key", "job_profiles", type_="unique")
    op.drop_column("job_profiles", "request_key")
    op.drop_constraint("uq_jobs_org_idempotency_key", "jobs", type_="unique")
    op.drop_column("jobs", "source_file_error")
    op.drop_column("jobs", "source_file_status")
    op.drop_column("jobs", "source_file_text")
    op.drop_column("jobs", "source_file_sha256")
    op.drop_column("jobs", "source_file_name")
    op.drop_column("jobs", "source_file_uri")
    op.drop_column("jobs", "idempotency_key")
    op.drop_column("jobs", "description_text")
