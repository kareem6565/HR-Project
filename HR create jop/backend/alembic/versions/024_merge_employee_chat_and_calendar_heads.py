"""Merge employee chatbot and Google Calendar migration heads.

Revision ID: 024_merge_employee_chat_calendar
Revises: 023_leave_workflow_history, 022_google_oauth_states
Create Date: 2026-11-17
"""

from __future__ import annotations

revision: str = "024_merge_employee_chat_calendar"
down_revision: tuple[str, str] = (
    "023_leave_workflow_history",
    "022_google_oauth_states",
)
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
