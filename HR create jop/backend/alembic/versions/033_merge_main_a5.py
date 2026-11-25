"""Join the main interview/calendar history with the A5/OCR migration line.

The existing development database may already be at ``029_hera_feature_merge``.
Keep that revision in the graph so Alembic can apply only the missing additive
HR password, SSO, retention, pre-ranking, and OCR migrations before this merge.
"""

from collections.abc import Sequence

revision: str = "033_merge_main_a5"
down_revision: str | Sequence[str] | None = (
    "029_hera_feature_merge",
    "032_resume_ocr_metadata",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
