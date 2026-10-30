"""store multiple workspace roles for one organization-scoped user

Revision ID: 018_dual_workspace_roles
Revises: 017_question_review
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "018_dual_workspace_roles"
down_revision: str | None = "019_interview_portal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("roles", sa.JSON(), nullable=True))

    bind = op.get_bind()
    users = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("role", sa.String()),
        sa.column("roles", sa.JSON()),
    )
    for user_id, role in bind.execute(sa.select(users.c.id, users.c.role)):
        bind.execute(
            users.update().where(users.c.id == user_id).values(roles=[role] if role else [])
        )

    op.alter_column(
        "users",
        "roles",
        existing_type=sa.JSON(),
        nullable=False,
        server_default=sa.text("'[]'"),
    )


def downgrade() -> None:
    op.drop_column("users", "roles")
