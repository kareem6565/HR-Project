"""Add candidate legal holds and organization retention policy defaults."""

import sqlalchemy as sa

from alembic import op

revision = "030_privacy_retention"
down_revision = "029_hr_sso_single_use"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("legal_hold", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("candidates", sa.Column("anonymized_at", sa.DateTime(timezone=True)))
    op.add_column(
        "organizations",
        sa.Column("rejected_retention_months", sa.Integer(), server_default="12", nullable=False),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "talent_pool_retention_months", sa.Integer(), server_default="24", nullable=False
        ),
    )
    op.create_check_constraint(
        "ck_organizations_rejected_retention_months",
        "organizations",
        "rejected_retention_months BETWEEN 1 AND 120",
    )
    op.create_check_constraint(
        "ck_organizations_talent_pool_retention_months",
        "organizations",
        "talent_pool_retention_months BETWEEN 1 AND 120",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_organizations_talent_pool_retention_months", "organizations", type_="check"
    )
    op.drop_constraint("ck_organizations_rejected_retention_months", "organizations", type_="check")
    op.drop_column("organizations", "talent_pool_retention_months")
    op.drop_column("organizations", "rejected_retention_months")
    op.drop_column("candidates", "anonymized_at")
    op.drop_column("candidates", "legal_hold")
