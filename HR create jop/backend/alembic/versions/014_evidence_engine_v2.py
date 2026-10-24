"""add evidence_engine_version to candidate_evaluations

Revision ID: 014_evidence_engine_v2
Revises: 013_screening_batches
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014_evidence_engine_v2"
down_revision: str | None = "013_screening_batches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_evaluations",
        sa.Column(
            "evidence_engine_version",
            sa.String(length=50),
            nullable=True,
            server_default=sa.text("'2.0'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("candidate_evaluations", "evidence_engine_version")
