"""Join the current recruitment migrations with the EPIC 6 interview branch."""

from collections.abc import Sequence

revision: str = "028_hera_interview_merge"
down_revision: str | Sequence[str] | None = ("027_ai_free_first", "022_google_oauth_states")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
