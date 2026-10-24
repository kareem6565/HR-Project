"""create workflow ai traces

Revision ID: 004_workflow_ai_traces
Revises: 003_eval_evidence_decisions
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004_workflow_ai_traces"
down_revision: str | None = "003_eval_evidence_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("related_entity_type", sa.String(length=50), nullable=True),
        sa.Column("related_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ("
            "'pending', 'running', 'waiting_for_human', 'completed', 'failed', 'cancelled'"
            ")",
            name="ck_workflow_runs_status",
        ),
        sa.CheckConstraint(
            "related_entity_type IS NULL OR related_entity_type IN ("
            "'job', 'candidate', 'resume', 'job_application', 'job_profile', "
            "'candidate_profile', 'candidate_evaluation'"
            ")",
            name="ck_workflow_runs_related_entity_type",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_runs_organization_id_status",
        "workflow_runs",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_workflow_runs_workflow_type_status",
        "workflow_runs",
        ["workflow_type", "status"],
    )
    op.create_index(
        "ix_workflow_runs_related_entity_type_id",
        "workflow_runs",
        ["related_entity_type", "related_entity_id"],
    )

    op.create_table(
        "workflow_step_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_type", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'skipped')",
            name="ck_workflow_step_traces_status",
        ),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_step_traces_workflow_run_id",
        "workflow_step_traces",
        ["workflow_run_id"],
    )
    op.create_index(
        "ix_workflow_step_traces_workflow_run_id_status",
        "workflow_step_traces",
        ["workflow_run_id", "status"],
    )
    op.create_index(
        "ix_workflow_step_traces_step_name_status",
        "workflow_step_traces",
        ["step_name", "status"],
    )

    op.create_table(
        "ai_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_step_trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_component_name", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=True),
        sa.Column("input_schema_version", sa.String(length=100), nullable=True),
        sa.Column("output_schema_version", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('started', 'succeeded', 'failed', 'validation_failed', 'retried')",
            name="ck_ai_traces_status",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_step_trace_id"], ["workflow_step_traces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_traces_workflow_step_trace_id",
        "ai_traces",
        ["workflow_step_trace_id"],
    )
    op.create_index(
        "ix_ai_traces_ai_component_name_status",
        "ai_traces",
        ["ai_component_name", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_traces_ai_component_name_status", table_name="ai_traces")
    op.drop_index("ix_ai_traces_workflow_step_trace_id", table_name="ai_traces")
    op.drop_table("ai_traces")

    op.drop_index("ix_workflow_step_traces_step_name_status", table_name="workflow_step_traces")
    op.drop_index(
        "ix_workflow_step_traces_workflow_run_id_status",
        table_name="workflow_step_traces",
    )
    op.drop_index("ix_workflow_step_traces_workflow_run_id", table_name="workflow_step_traces")
    op.drop_table("workflow_step_traces")

    op.drop_index("ix_workflow_runs_related_entity_type_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_workflow_type_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_organization_id_status", table_name="workflow_runs")
    op.drop_table("workflow_runs")
