"""epic 6 google calendar, outbox, reservations, and rescheduling foundations

Revision ID: 021_epic6_calendar
Revises: 020_hr_ops_schema
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021_epic6_calendar"
down_revision: str | None = "020_hr_ops_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "hr_google_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("google_email", sa.String(length=255), nullable=True),
        sa.Column("calendar_id", sa.String(length=255), nullable=False, server_default="primary"),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="connected"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_hr_google_connection_org_user"),
    )
    op.create_index(
        "ix_hr_google_connections_org_user",
        "hr_google_connections",
        ["organization_id", "user_id"],
        unique=False,
    )

    op.create_table(
        "transactional_email_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("template", sa.String(length=120), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="console"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'processing', 'sent', 'failed')", name="ck_email_outbox_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_outbox_status_next",
        "transactional_email_outbox",
        ["status", "next_attempt_at", "created_at"],
        unique=False,
    )

    op.create_table(
        "calendar_sync_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hr_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation", sa.String(length=40), nullable=False),  # upsert/cancel
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'processing', 'succeeded', 'failed')", name="ck_calendar_outbox_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["hr_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_calendar_outbox_idempotency"),
    )
    op.create_index(
        "ix_calendar_outbox_status_next",
        "calendar_sync_outbox",
        ["status", "next_attempt_at", "created_at"],
        unique=False,
    )

    op.add_column("interviews", sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("interviews", sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("interviews", sa.Column("google_calendar_id", sa.String(length=255), nullable=True))
    op.add_column("interviews", sa.Column("google_event_id", sa.String(length=255), nullable=True))
    op.add_column(
        "interviews",
        sa.Column("calendar_sync_status", sa.String(length=30), nullable=False, server_default="not_required"),
    )
    op.add_column("interviews", sa.Column("calendar_sync_error", sa.String(length=1000), nullable=True))

    # Historical rows are left with NULL scheduled_start_at/end_at intentionally:
    # naive scheduled_date/scheduled_time have no proven timezone contract, so this
    # migration must not invent or silently backfill historical instants.
    op.create_index("ix_interviews_scheduled_start_at", "interviews", ["scheduled_start_at"], unique=False)

    op.add_column(
        "candidate_invitations",
        sa.Column("reschedule_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "candidate_invitations",
        sa.Column("last_rescheduled_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "interview_slot_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interviewer_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),  # active/released
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active', 'released')", name="ck_interview_reservations_status"),
        sa.CheckConstraint("scheduled_end_at > scheduled_start_at", name="ck_interview_reservations_range"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["interviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_reservations_interview", "interview_slot_reservations", ["interview_id"], unique=False)
    op.create_index("ix_interview_reservations_org", "interview_slot_reservations", ["organization_id", "status"], unique=False)

    # DB-enforced overlap protection for active reservations
    op.execute(
        """
        ALTER TABLE interview_slot_reservations
        ADD CONSTRAINT ex_interview_reservations_interviewer
        EXCLUDE USING gist (
            interviewer_user_id WITH =,
            tstzrange(scheduled_start_at, scheduled_end_at, '[)') WITH &&
        )
        WHERE (status = 'active' AND interviewer_user_id IS NOT NULL)
        """
    )
    op.execute(
        """
        ALTER TABLE interview_slot_reservations
        ADD CONSTRAINT ex_interview_reservations_candidate
        EXCLUDE USING gist (
            candidate_id WITH =,
            tstzrange(scheduled_start_at, scheduled_end_at, '[)') WITH &&
        )
        WHERE (status = 'active')
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE interview_slot_reservations DROP CONSTRAINT IF EXISTS ex_interview_reservations_candidate")
    op.execute("ALTER TABLE interview_slot_reservations DROP CONSTRAINT IF EXISTS ex_interview_reservations_interviewer")
    op.drop_index("ix_interview_reservations_org", table_name="interview_slot_reservations")
    op.drop_index("ix_interview_reservations_interview", table_name="interview_slot_reservations")
    op.drop_table("interview_slot_reservations")

    op.drop_column("candidate_invitations", "last_rescheduled_at")
    op.drop_column("candidate_invitations", "reschedule_count")

    op.drop_index("ix_interviews_scheduled_start_at", table_name="interviews")
    op.drop_column("interviews", "calendar_sync_error")
    op.drop_column("interviews", "calendar_sync_status")
    op.drop_column("interviews", "google_event_id")
    op.drop_column("interviews", "google_calendar_id")
    op.drop_column("interviews", "scheduled_end_at")
    op.drop_column("interviews", "scheduled_start_at")

    op.drop_index("ix_calendar_outbox_status_next", table_name="calendar_sync_outbox")
    op.drop_table("calendar_sync_outbox")

    op.drop_index("ix_email_outbox_status_next", table_name="transactional_email_outbox")
    op.drop_table("transactional_email_outbox")

    op.drop_index("ix_hr_google_connections_org_user", table_name="hr_google_connections")
    op.drop_table("hr_google_connections")
