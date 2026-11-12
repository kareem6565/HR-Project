"""Queue public applications in the existing screening pipeline."""

import sqlalchemy as sa

from alembic import op

revision = "023_public_application_screening"
down_revision = "022_public_candidate_apps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "screening_batch_items",
        sa.Column("source", sa.String(32), nullable=False, server_default="manual_upload"),
    )
    op.add_column(
        "screening_batch_items", sa.Column("job_profile_id", sa.Uuid(), nullable=True)
    )
    op.create_check_constraint(
        "ck_screening_batch_items_source", "screening_batch_items",
        "source IN ('manual_upload', 'public_application')",
    )
    op.create_foreign_key(
        "fk_screening_batch_items_job_profile_id_job_profiles",
        "screening_batch_items", "job_profiles", ["job_profile_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(
        "uq_screening_batch_items_public_application", "screening_batch_items", ["application_id"],
        unique=True,
        postgresql_where=sa.text("source = 'public_application' AND application_id IS NOT NULL"),
        sqlite_where=sa.text("source = 'public_application' AND application_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_screening_batch_items_public_application", table_name="screening_batch_items")
    op.drop_constraint(
        "fk_screening_batch_items_job_profile_id_job_profiles",
        "screening_batch_items",
        type_="foreignkey",
    )
    op.drop_constraint("ck_screening_batch_items_source", "screening_batch_items", type_="check")
    op.drop_column("screening_batch_items", "job_profile_id")
    op.drop_column("screening_batch_items", "source")
