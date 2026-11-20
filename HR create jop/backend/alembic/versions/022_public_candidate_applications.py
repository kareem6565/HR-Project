"""Add public candidate application metadata and rate limiting."""

import sqlalchemy as sa

from alembic import op

revision = "022_public_candidate_apps"
down_revision = "021_public_job_publishing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for _, column in (
        ("public_reference", sa.Column("public_reference", sa.String(48), nullable=True)),
        ("idempotency_key_hash", sa.Column("idempotency_key_hash", sa.String(64), nullable=True)),
        ("source", sa.Column("source", sa.String(100), nullable=True)),
        ("source_medium", sa.Column("source_medium", sa.String(100), nullable=True)),
        ("source_campaign", sa.Column("source_campaign", sa.String(100), nullable=True)),
        ("linkedin_url", sa.Column("linkedin_url", sa.Text(), nullable=True)),
        ("github_url", sa.Column("github_url", sa.Text(), nullable=True)),
        ("portfolio_url", sa.Column("portfolio_url", sa.Text(), nullable=True)),
        (
            "privacy_notice_accepted",
            sa.Column(
                "privacy_notice_accepted", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        ),
        (
            "privacy_notice_version",
            sa.Column("privacy_notice_version", sa.String(80), nullable=True),
        ),
        ("privacy_notice_text", sa.Column("privacy_notice_text", sa.Text(), nullable=True)),
        (
            "privacy_notice_accepted_at",
            sa.Column("privacy_notice_accepted_at", sa.DateTime(timezone=True), nullable=True),
        ),
        ("public_contact_email", sa.Column("public_contact_email", sa.String(255), nullable=True)),
    ):
        op.add_column("job_applications", column)
    op.create_unique_constraint(
        "uq_job_applications_public_reference", "job_applications", ["public_reference"]
    )
    op.create_unique_constraint(
        "uq_job_applications_idempotency",
        "job_applications",
        ["organization_id", "job_id", "idempotency_key_hash"],
    )
    op.create_table(
        "public_application_rate_limits",
        sa.Column("fingerprint_hash", sa.String(64), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submission_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_public_application_rate_limits_window",
        "public_application_rate_limits",
        ["window_started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_public_application_rate_limits_window", table_name="public_application_rate_limits"
    )
    op.drop_table("public_application_rate_limits")
    op.drop_constraint("uq_job_applications_idempotency", "job_applications", type_="unique")
    op.drop_constraint("uq_job_applications_public_reference", "job_applications", type_="unique")
    for name in (
        "privacy_notice_accepted_at",
        "public_contact_email",
        "privacy_notice_text",
        "privacy_notice_version",
        "privacy_notice_accepted",
        "portfolio_url",
        "github_url",
        "linkedin_url",
        "source_campaign",
        "source_medium",
        "source",
        "idempotency_key_hash",
        "public_reference",
    ):
        op.drop_column("job_applications", name)
