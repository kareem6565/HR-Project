"""hash interview invitation tokens and retain candidate booking receipt

Revision ID: 019_interview_portal
Revises: 018_talent_pool_consent
Create Date: 2026-10-25
"""

from collections.abc import Sequence
import hashlib

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "019_interview_portal"
down_revision: str | None = "018_talent_pool_consent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_invitations",
        sa.Column("token_hash", sa.String(length=64), nullable=True),
    )
    bind = op.get_bind()
    invitations = sa.table(
        "candidate_invitations",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("token", sa.String(length=64)),
        sa.column("token_hash", sa.String(length=64)),
    )
    for row in bind.execute(sa.select(invitations.c.id, invitations.c.token)):
        bind.execute(
            invitations.update()
            .where(invitations.c.id == row.id)
            .values(token_hash=hashlib.sha256(row.token.encode("utf-8")).hexdigest())
        )

    op.alter_column("candidate_invitations", "token_hash", nullable=False)
    op.drop_index("ix_candidate_invitations_token", table_name="candidate_invitations")
    op.drop_column("candidate_invitations", "token")
    op.create_index(
        "ix_candidate_invitations_token_hash",
        "candidate_invitations",
        ["token_hash"],
        unique=True,
    )
    op.add_column(
        "candidate_invitations",
        sa.Column("booked_interview_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "candidate_invitations",
        sa.Column("booked_availability_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_candidate_invitation_booked_interview",
        "candidate_invitations",
        "interviews",
        ["booked_interview_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_candidate_invitation_booked_availability",
        "candidate_invitations",
        "interview_availabilities",
        ["booked_availability_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade is intentionally unsupported: raw invitation tokens cannot be recovered."
    )
