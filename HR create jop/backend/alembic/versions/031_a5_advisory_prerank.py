"""Add advisory pre-ranking configuration and application metadata."""

import sqlalchemy as sa

from alembic import op

revision = "031_a5_advisory_prerank"
down_revision = "030_privacy_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs", sa.Column("prerank_top_n", sa.Integer(), server_default="20", nullable=False)
    )
    op.create_check_constraint("ck_jobs_prerank_top_n", "jobs", "prerank_top_n BETWEEN 1 AND 100")
    op.add_column("job_applications", sa.Column("advisory_rank", sa.Integer(), nullable=True))
    op.add_column("job_applications", sa.Column("advisory_score", sa.Float(), nullable=True))
    op.add_column(
        "job_applications", sa.Column("advisory_status", sa.String(length=32), nullable=True)
    )
    op.add_column("job_applications", sa.Column("advisory_message", sa.Text(), nullable=True))
    op.add_column("screening_batch_items", sa.Column("advisory_rank", sa.Integer(), nullable=True))
    op.add_column("screening_batch_items", sa.Column("advisory_score", sa.Float(), nullable=True))
    op.add_column(
        "screening_batch_items", sa.Column("advisory_status", sa.String(length=32), nullable=True)
    )
    op.add_column("screening_batch_items", sa.Column("advisory_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("screening_batch_items", "advisory_message")
    op.drop_column("screening_batch_items", "advisory_status")
    op.drop_column("screening_batch_items", "advisory_score")
    op.drop_column("screening_batch_items", "advisory_rank")
    op.drop_column("job_applications", "advisory_message")
    op.drop_column("job_applications", "advisory_status")
    op.drop_column("job_applications", "advisory_score")
    op.drop_column("job_applications", "advisory_rank")
    op.drop_constraint("ck_jobs_prerank_top_n", "jobs", type_="check")
    op.drop_column("jobs", "prerank_top_n")
