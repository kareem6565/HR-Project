"""Join interview and employee chatbot migrations with the current recruitment chain."""

from collections.abc import Sequence

revision: str = "029_hera_feature_merge"
down_revision: str | Sequence[str] | None = (
    "028_hera_interview_merge",
    "024_merge_employee_chat_calendar",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
