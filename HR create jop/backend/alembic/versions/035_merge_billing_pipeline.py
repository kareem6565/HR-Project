"""Join current main billing and recruitment pipeline migration heads."""

from collections.abc import Sequence

revision: str = "035_merge_billing_pipeline"
down_revision: str | Sequence[str] | None = ("032_billing_subscriptions", "034_pipeline_stages")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge the independent billing and pipeline histories without schema changes."""


def downgrade() -> None:
    """Re-expose both parent heads when this graph-only merge is downgraded."""
