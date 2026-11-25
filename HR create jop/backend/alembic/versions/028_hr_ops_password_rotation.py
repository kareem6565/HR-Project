"""Require seeded HR Manager accounts to rotate their initial password."""

import sqlalchemy as sa

from alembic import op

revision = "028_hr_ops_pw_rotate"
down_revision = "027_ai_free_first"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="hr_ops",
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password", schema="hr_ops")
