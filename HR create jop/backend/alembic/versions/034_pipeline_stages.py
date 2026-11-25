"""Add the human-controlled pipeline stage and transition history."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "034_pipeline_stages"
down_revision: str | Sequence[str] | None = "033_merge_main_a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAGE_FOR_STATUS = {
    "created": "screening",
    "analysis_pending": "screening",
    "analyzing": "screening",
    "analysis_failed": "screening",
    "ready_for_review": "review",
    "hold": "review",
    "advanced": "review",
    "rejected": "rejected",
    "archived": "archived",
}
BATCH_SIZE = 500


def _stage_for(status: str, has_interview: bool) -> str:
    stage = STAGE_FOR_STATUS.get(status)
    if stage is None:
        raise RuntimeError(f"Unknown job application status in pipeline migration: {status!r}")
    if status in {"hold", "advanced"} and has_interview:
        return "interview"
    return stage


def upgrade() -> None:
    bind = op.get_bind()
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "pipeline_stage_transitions",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            uuid_type,
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "job_application_id",
            uuid_type,
            sa.ForeignKey("job_applications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("from_stage", sa.String(length=24), nullable=True),
        sa.Column("to_stage", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "job_application_id",
            "actor_user_id",
            "idempotency_key",
            name="uq_pipeline_stage_transitions_idempotency",
        ),
    )
    op.create_index(
        "ix_pipeline_stage_transitions_org_application_created",
        "pipeline_stage_transitions",
        ["organization_id", "job_application_id", "created_at"],
    )

    op.add_column(
        "job_applications", sa.Column("pipeline_stage", sa.String(length=24), nullable=True)
    )

    applications = sa.table(
        "job_applications",
        sa.column("id", uuid_type),
        sa.column("organization_id", uuid_type),
        sa.column("status", sa.String(length=50)),
        sa.column("pipeline_stage", sa.String(length=24)),
    )
    interviews = sa.table(
        "interviews",
        sa.column("id", uuid_type),
        sa.column("job_application_id", uuid_type),
    )
    transitions = sa.table(
        "pipeline_stage_transitions",
        sa.column("id", uuid_type),
        sa.column("organization_id", uuid_type),
        sa.column("job_application_id", uuid_type),
        sa.column("actor_user_id", uuid_type),
        sa.column("from_stage", sa.String(length=24)),
        sa.column("to_stage", sa.String(length=24)),
        sa.column("reason_code", sa.String(length=80)),
        sa.column("note", sa.Text()),
        sa.column("source", sa.String(length=32)),
        sa.column("idempotency_key", uuid_type),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    last_id = None
    while True:
        statement = (
            sa.select(
                applications.c.id,
                applications.c.organization_id,
                applications.c.status,
                sa.exists(
                    sa.select(1).where(interviews.c.job_application_id == applications.c.id)
                ).label("has_interview"),
            )
            .order_by(applications.c.id)
            .limit(BATCH_SIZE)
        )
        if last_id is not None:
            statement = statement.where(applications.c.id > last_id)
        rows = list(bind.execute(statement))
        if not rows:
            break

        inserted_at = datetime.now(UTC)
        stage_rows = []
        for row in rows:
            stage = _stage_for(row.status, bool(row.has_interview))
            stage_rows.append(
                {
                    "id": row.id,
                    "organization_id": row.organization_id,
                    "job_application_id": row.id,
                    "actor_user_id": None,
                    "from_stage": None,
                    "to_stage": stage,
                    "reason_code": "migration_baseline",
                    "note": None,
                    "source": "migration",
                    "idempotency_key": None,
                    # This is when the baseline was recorded, not a historical transition time.
                    "created_at": inserted_at,
                }
            )
        bind.execute(
            sa.update(applications)
            .where(applications.c.id.in_([row.id for row in rows]))
            .values(
                pipeline_stage=sa.case(
                    {row.id: _stage_for(row.status, bool(row.has_interview)) for row in rows},
                    value=applications.c.id,
                )
            )
        )
        bind.execute(sa.insert(transitions), stage_rows)
        last_id = rows[-1].id

    with op.batch_alter_table("job_applications") as batch_op:
        batch_op.alter_column(
            "pipeline_stage",
            existing_type=sa.String(length=24),
            nullable=False,
            server_default="screening",
        )
        batch_op.create_check_constraint(
            "ck_job_applications_status_pipeline_stage",
            "(status = 'rejected' AND pipeline_stage = 'rejected') OR "
            "(status = 'archived' AND pipeline_stage = 'archived') OR "
            "(status NOT IN ('rejected', 'archived') AND pipeline_stage IN "
            "('screening', 'review', 'interview', 'offer', 'hired', 'withdrawn'))",
        )


def downgrade() -> None:
    op.drop_index(
        "ix_pipeline_stage_transitions_org_application_created",
        table_name="pipeline_stage_transitions",
    )
    op.drop_table("pipeline_stage_transitions")
    with op.batch_alter_table("job_applications") as batch_op:
        batch_op.drop_constraint("ck_job_applications_status_pipeline_stage", type_="check")
        batch_op.drop_column("pipeline_stage")
