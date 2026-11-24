"""add short-lived one-time google oauth state records

Revision ID: 022_google_oauth_states
Revises: 021_epic6_calendar
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "022_google_oauth_states"
down_revision: str | None = "021_epic6_calendar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hr_google_oauth_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_hr_google_oauth_states_token_hash"),
    )
    op.create_index(
        "ix_hr_google_oauth_states_expires_at",
        "hr_google_oauth_states",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_hr_google_oauth_states_org_user",
        "hr_google_oauth_states",
        ["organization_id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hr_google_oauth_states_org_user", table_name="hr_google_oauth_states")
    op.drop_index("ix_hr_google_oauth_states_expires_at", table_name="hr_google_oauth_states")
    op.drop_table("hr_google_oauth_states")
