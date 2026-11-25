"""External candidate sourcing searches and suggested profiles."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "030_sourcing"
down_revision = "029_hera_feature_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sourcing_searches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=48), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("actor_run_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_code", sa.String(length=48), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_sourcing_searches_status",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sourcing_searches_org_status",
        "sourcing_searches",
        ["organization_id", "status"],
    )
    op.create_table(
        "sourcing_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("search_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("headline", sa.String(length=512), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("current_title", sa.String(length=255), nullable=True),
        sa.Column("current_company", sa.String(length=255), nullable=True),
        sa.Column("profile_url", sa.String(length=512), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fit_score", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('suggested', 'added_to_pipeline', 'dismissed')",
            name="ck_sourcing_candidates_status",
        ),
        sa.ForeignKeyConstraint(["search_id"], ["sourcing_searches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sourcing_candidates_search", "sourcing_candidates", ["search_id"])


def downgrade() -> None:
    op.drop_index("ix_sourcing_candidates_search", table_name="sourcing_candidates")
    op.drop_table("sourcing_candidates")
    op.drop_index("ix_sourcing_searches_org_status", table_name="sourcing_searches")
    op.drop_table("sourcing_searches")
