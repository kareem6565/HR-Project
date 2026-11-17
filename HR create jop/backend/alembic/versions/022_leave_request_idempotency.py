"""Add request keys to make chatbot leave submission retries safe.

Revision ID: 022_leave_request_idempotency
Revises: 021_employee_policy_sections
Create Date: 2026-11-12
"""

from __future__ import annotations

from alembic import op

revision: str = "022_leave_request_idempotency"
down_revision: str | None = "021_employee_policy_sections"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE hr_ops.leave_requests ADD COLUMN request_key varchar(64)")
    op.execute(
        "CREATE UNIQUE INDEX uq_leave_requests_request_key "
        "ON hr_ops.leave_requests (request_key) WHERE request_key IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS hr_ops.uq_leave_requests_request_key")
    op.execute("ALTER TABLE hr_ops.leave_requests DROP COLUMN request_key")
