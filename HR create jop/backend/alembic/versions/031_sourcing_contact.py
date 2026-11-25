"""Contact fields on sourced candidates (email from provider search, rare phone)."""

import sqlalchemy as sa

from alembic import op

revision = "031_sourcing_contact"
down_revision = "030_sourcing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sourcing_candidates", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("sourcing_candidates", sa.Column("phone", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("sourcing_candidates", "phone")
    op.drop_column("sourcing_candidates", "email")
