"""Join the current recruitment migrations with the EPIC 6 interview branch."""

revision = "028_hera_interview_merge"
down_revision = ("027_ai_free_first", "022_google_oauth_states")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
