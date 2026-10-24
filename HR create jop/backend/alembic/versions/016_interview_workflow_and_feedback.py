"""add interview_availabilities, candidate_invitations, and hr_feedback_corrections tables

Revision ID: 016_interview_workflow
Revises: 015_audit_logs
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016_interview_workflow"
down_revision: str | None = "015_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. interview_availabilities
    op.create_table(
        "interview_availabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interviewer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.String(length=20), nullable=False),
        sa.Column("end_time", sa.String(length=20), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("timezone", sa.String(length=50), nullable=False, server_default="UTC"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="available"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["interviewer_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('available', 'booked', 'cancelled')",
            name="ck_interview_availabilities_status",
        ),
    )
    op.create_index(
        "ix_interview_avail_org_date",
        "interview_availabilities",
        ["organization_id", "scheduled_date"],
    )
    op.create_index(
        "ix_interview_avail_interviewer",
        "interview_availabilities",
        ["interviewer_user_id", "scheduled_date"],
    )

    # 2. candidate_invitations
    op.create_table(
        "candidate_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["job_application_id"], ["job_applications.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'booked', 'expired', 'cancelled')",
            name="ck_candidate_invitations_status",
        ),
    )
    op.create_index("ix_candidate_invitations_token", "candidate_invitations", ["token"], unique=True)
    op.create_index("ix_candidate_invitations_app", "candidate_invitations", ["job_application_id"])
    op.create_index("ix_candidate_invitations_org", "candidate_invitations", ["organization_id"])

    # 3. hr_feedback_corrections
    op.create_table(
        "hr_feedback_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correction_type", sa.String(length=50), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_evaluation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "original_ai_output",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column(
            "hr_corrected_result",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "evidence_reference",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column(
            "provider_info",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["job_profile_id"], ["job_profiles.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["candidate_profile_id"], ["candidate_profiles.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["candidate_evaluation_id"], ["candidate_evaluations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["job_application_id"], ["job_applications.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "correction_type IN ("
            "'extraction_correction', "
            "'skill_alias_correction', "
            "'requirement_match_correction', "
            "'scoring_rule_correction', "
            "'recommendation_override', "
            "'final_decision', "
            "'interview_feedback_correction', "
            "'post_interview_decision'"
            ")",
            name="ck_hr_feedback_corrections_type",
        ),
    )
    op.create_index(
        "ix_hr_feedback_org_type",
        "hr_feedback_corrections",
        ["organization_id", "correction_type"],
    )
    op.create_index(
        "ix_hr_feedback_eval",
        "hr_feedback_corrections",
        ["candidate_evaluation_id"],
    )
    op.create_index(
        "ix_hr_feedback_created",
        "hr_feedback_corrections",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("hr_feedback_corrections")
    op.drop_table("candidate_invitations")
    op.drop_table("interview_availabilities")
