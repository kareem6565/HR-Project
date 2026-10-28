"""record explicit candidate consent for talent-pool reuse

Revision ID: 018_talent_pool_consent
Revises: 017_question_review
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018_talent_pool_consent"
down_revision: str | None = "017_question_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "talent_pool_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("link_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("link_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response", sa.String(length=20), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_text", sa.Text(), nullable=True),
        sa.Column("consent_version", sa.String(length=40), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "response IS NULL OR response IN ('accepted', 'declined')",
            name="ck_talent_pool_consents_response",
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_talent_pool_consents_token_hash"),
    )
    op.create_index(
        "ix_talent_pool_consents_candidate_org",
        "talent_pool_consents",
        ["candidate_id", "organization_id"],
    )
    op.create_index(
        "ix_talent_pool_consents_org_expiry",
        "talent_pool_consents",
        ["organization_id", "consent_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_talent_pool_consents_org_expiry", table_name="talent_pool_consents")
    op.drop_index("ix_talent_pool_consents_candidate_org", table_name="talent_pool_consents")
    op.drop_table("talent_pool_consents")
