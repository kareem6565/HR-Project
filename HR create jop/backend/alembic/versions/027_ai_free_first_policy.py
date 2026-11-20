"""Add shared AI request metering and cost circuit breaker."""

import sqlalchemy as sa

from alembic import op

revision = "027_ai_free_first"
down_revision = "026_github_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("feature", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("provider_request_id", sa.String(length=160), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("reported_cost_usd", sa.Numeric(14, 10), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('started', 'succeeded', 'failed', 'cost_alert')",
            name="ck_ai_usage_events_status",
        ),
        sa.CheckConstraint(
            "reported_cost_usd IS NULL OR reported_cost_usd >= 0",
            name="ck_ai_usage_events_cost",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_usage_events_created_at", "ai_usage_events", ["created_at"])
    op.create_index("ix_ai_usage_events_user_created", "ai_usage_events", ["user_id", "created_at"])
    op.create_table(
        "ai_usage_counters",
        sa.Column("bucket_key", sa.String(length=180), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("bucket_key"),
    )
    op.create_table(
        "ai_policy_controls",
        sa.Column("control_key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("control_key"),
    )


def downgrade() -> None:
    op.drop_table("ai_policy_controls")
    op.drop_table("ai_usage_counters")
    op.drop_index("ix_ai_usage_events_user_created", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_created_at", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
