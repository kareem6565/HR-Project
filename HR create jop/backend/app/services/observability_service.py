"""Observability read/query service (Phase 3.8).

Provides deterministic, read-only query helpers over the existing workflow,
step, and AI trace tables (WorkflowRun, WorkflowStepTrace, AITrace). It answers
questions about workflow/step/AI durations, AI provider/model and schema usage,
AI call outcomes, failed workflows and their root causes, and provenance
references/hashes — without exposing raw candidate or job content.

This service is strictly a read layer:
- It never creates, modifies, or deletes workflow runs, step traces, or AI
  traces.
- It never commits (the caller owns the transaction).
- It never invokes an AI provider or an AI workflow and never touches domain
  artifacts.

Organization isolation is enforced by scoping every lookup through the owning
WorkflowRun's ``organization_id`` whenever ``organization_id`` is supplied,
mirroring the conventions established in Phases 3.1-3.7.

Duration is derived from existing timestamps (``started_at``/``completed_at``)
or, for AI calls, the existing ``latency_ms`` field. No duration columns are
added. Running/incomplete records (missing ``completed_at``) are handled
safely by returning ``None`` for the derived duration.

Failure classification reports only what the existing schema supports: step
failures carry ``error_type``/``error_message``, and AI trace statuses natively
distinguish ``failed`` from ``validation_failed`` (plus ``succeeded``,
``started``, and ``retried``). No second error taxonomy is invented.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AITrace, WorkflowRun, WorkflowStepTrace
from app.services.errors import NotFoundError, ValidationError

DEFAULT_LIST_LIMIT = 100


def _duration_seconds(started_at: datetime | None, completed_at: datetime | None) -> float | None:
    """Return the wall-clock duration in seconds when both timestamps exist."""
    if started_at is None or completed_at is None:
        return None
    return (completed_at - started_at).total_seconds()


def _ai_status_counts(traces: list[AITrace]) -> tuple[int, int, int]:
    """Return (succeeded, failed, validation_failed) counts for AI traces."""
    succeeded = 0
    failed = 0
    validation_failed = 0
    for trace in traces:
        if trace.status == "succeeded":
            succeeded += 1
        elif trace.status == "failed":
            failed += 1
        elif trace.status == "validation_failed":
            validation_failed += 1
    return succeeded, failed, validation_failed


@dataclass(frozen=True)
class WorkflowRunSummary:
    """A sanitized, aggregated view of one workflow run."""

    workflow_run_id: uuid.UUID
    workflow_type: str
    status: str
    organization_id: uuid.UUID
    related_entity_type: str | None
    related_entity_id: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    step_count: int
    ai_call_count: int
    ai_succeeded: int
    ai_failed: int
    ai_validation_failed: int


@dataclass(frozen=True)
class AIFailureSummary:
    """Aggregated counts of AI trace outcomes."""

    succeeded: int
    failed: int
    validation_failed: int
    total: int


class ObservabilityService:
    """Read-only query helpers over workflow, step, and AI trace records."""

    def get_workflow_run(
        self,
        db: Session,
        *,
        workflow_run_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> WorkflowRun:
        """Return one workflow run, enforcing organization scope when supplied."""
        run = db.get(WorkflowRun, workflow_run_id)
        if run is None:
            raise NotFoundError("WorkflowRun was not found.")
        if organization_id is not None and run.organization_id != organization_id:
            raise ValidationError("WorkflowRun belongs to a different organization.")
        return run

    def get_workflow_step_trace(
        self,
        db: Session,
        *,
        workflow_step_trace_id: uuid.UUID,
        workflow_run_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> WorkflowStepTrace:
        """Return one step trace, optionally validating its run and organization."""
        step = db.get(WorkflowStepTrace, workflow_step_trace_id)
        if step is None:
            raise NotFoundError("WorkflowStepTrace was not found.")
        if workflow_run_id is not None and step.workflow_run_id != workflow_run_id:
            raise ValidationError("WorkflowStepTrace does not belong to the expected run.")
        if organization_id is not None:
            run = db.get(WorkflowRun, step.workflow_run_id)
            if run is None or run.organization_id != organization_id:
                raise NotFoundError("WorkflowStepTrace was not found.")
        return step

    def get_ai_trace(
        self,
        db: Session,
        *,
        ai_trace_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> AITrace:
        """Return one AI trace, enforcing organization scope when supplied."""
        trace = db.get(AITrace, ai_trace_id)
        if trace is None:
            raise NotFoundError("AITrace was not found.")
        if organization_id is not None:
            run = db.get(WorkflowRun, trace.workflow_step_trace.workflow_run_id)
            if run is None or run.organization_id != organization_id:
                raise NotFoundError("AITrace was not found.")
        return trace

    def list_workflow_steps(
        self,
        db: Session,
        *,
        workflow_run_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> list[WorkflowStepTrace]:
        """Return the step traces for a workflow run, ordered by created time."""
        run = self.get_workflow_run(
            db,
            workflow_run_id=workflow_run_id,
            organization_id=organization_id,
        )
        return list(
            db.scalars(
                select(WorkflowStepTrace)
                .where(WorkflowStepTrace.workflow_run_id == run.id)
                .order_by(WorkflowStepTrace.created_at, WorkflowStepTrace.step_name)
            )
        )

    def list_ai_traces(
        self,
        db: Session,
        *,
        workflow_step_trace_id: uuid.UUID | None = None,
        workflow_run_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> list[AITrace]:
        """Return AI traces for a step and/or a run, ordered by created time."""
        if workflow_step_trace_id is not None:
            step = self.get_workflow_step_trace(
                db,
                workflow_step_trace_id=workflow_step_trace_id,
                workflow_run_id=workflow_run_id,
                organization_id=organization_id,
            )
            statement = select(AITrace).where(AITrace.workflow_step_trace_id == step.id)
        elif workflow_run_id is not None:
            run = self.get_workflow_run(
                db,
                workflow_run_id=workflow_run_id,
                organization_id=organization_id,
            )
            statement = (
                select(AITrace)
                .join(WorkflowStepTrace, AITrace.workflow_step_trace_id == WorkflowStepTrace.id)
                .where(WorkflowStepTrace.workflow_run_id == run.id)
            )
        else:
            raise ValidationError("Either workflow_run_id or workflow_step_trace_id is required.")
        return list(db.scalars(statement.order_by(AITrace.created_at, AITrace.ai_component_name)))

    def get_workflow_summary(
        self,
        db: Session,
        *,
        workflow_run_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> WorkflowRunSummary:
        """Return a sanitized aggregate view of a workflow run."""
        run = self.get_workflow_run(
            db,
            workflow_run_id=workflow_run_id,
            organization_id=organization_id,
        )
        steps = self.list_workflow_steps(db, workflow_run_id=run.id)
        ai_traces = self.list_ai_traces(db, workflow_run_id=run.id)
        succeeded, failed, validation_failed = _ai_status_counts(ai_traces)
        return WorkflowRunSummary(
            workflow_run_id=run.id,
            workflow_type=run.workflow_type,
            status=run.status,
            organization_id=run.organization_id,
            related_entity_type=run.related_entity_type,
            related_entity_id=run.related_entity_id,
            started_at=run.started_at,
            completed_at=run.completed_at,
            duration_seconds=_duration_seconds(run.started_at, run.completed_at),
            step_count=len(steps),
            ai_call_count=len(ai_traces),
            ai_succeeded=succeeded,
            ai_failed=failed,
            ai_validation_failed=validation_failed,
        )

    def get_failed_workflows(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID | None = None,
        workflow_type: str | None = None,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[WorkflowRun]:
        """Return failed workflow runs, newest first, scoped when supplied."""
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.status == "failed")
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
        )
        if organization_id is not None:
            statement = statement.where(WorkflowRun.organization_id == organization_id)
        if workflow_type is not None:
            statement = statement.where(WorkflowRun.workflow_type == workflow_type)
        return list(db.scalars(statement))

    def get_ai_failure_summary(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID | None = None,
    ) -> AIFailureSummary:
        """Return aggregate AI trace outcome counts, scoped when supplied."""
        statement = select(AITrace)
        if organization_id is not None:
            statement = (
                statement.join(
                    WorkflowStepTrace,
                    AITrace.workflow_step_trace_id == WorkflowStepTrace.id,
                )
                .join(WorkflowRun, WorkflowStepTrace.workflow_run_id == WorkflowRun.id)
                .where(WorkflowRun.organization_id == organization_id)
            )
        traces = list(db.scalars(statement))
        succeeded, failed, validation_failed = _ai_status_counts(traces)
        return AIFailureSummary(
            succeeded=succeeded,
            failed=failed,
            validation_failed=validation_failed,
            total=len(traces),
        )
