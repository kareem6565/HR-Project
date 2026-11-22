"""Store consumed HERA SSO assertion identifiers."""

import sqlalchemy as sa

from alembic import op

revision = "029_hr_sso_single_use"
down_revision = "028_hr_ops_pw_rotate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_sso_assertion_uses",
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("jti_hash"),
    )
    op.create_index(
        "ix_hr_sso_assertion_uses_expires_at",
        "hr_sso_assertion_uses",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_hr_sso_assertion_uses_expires_at", table_name="hr_sso_assertion_uses")
    op.drop_table("hr_sso_assertion_uses")
