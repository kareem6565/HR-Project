from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AITrace,
    Candidate,
    CandidateEvaluation,
    CandidateProfile,
    ChatThread,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    WorkflowRun,
    WorkflowStepTrace,
)
from app.services.errors import NotFoundError, ValidationError


class WorkflowTraceService:
    """Deterministic persistence helpers for workflow, step, and AI trace records."""

    def start_run(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        workflow_type: str,
        related_entity_type: str | None = None,
        related_entity_id: uuid.UUID | None = None,
        status: str = "running",
    ) -> WorkflowRun:
        """Create a workflow run in pending or running state."""
        if status not in {"pending", "running"}:
            raise ValidationError("WorkflowRun must start as pending or running.")
        organization = db.get(Organization, organization_id)
        if organization is None:
            raise NotFoundError("Organization was not found.")
        self._validate_related_entity(
            db,
            organization_id=organization_id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )

        run = WorkflowRun(
            organization_id=organization_id,
            workflow_type=workflow_type,
            status=status,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            started_at=datetime.now(UTC) if status == "running" else None,
        )
        db.add(run)
        db.flush()
        return run

    def mark_run_running(self, db: Session, *, workflow_run_id: uuid.UUID) -> WorkflowRun:
        """Mark a workflow run as running."""
        run = self._get_run(db, workflow_run_id=workflow_run_id)
        run.status = "running"
        run.started_at = run.started_at or datetime.now(UTC)
        db.flush()
        return run

    def mark_run_waiting_for_human(
        self,
        db: Session,
        *,
        workflow_run_id: uuid.UUID,
    ) -> WorkflowRun:
        """Mark a workflow run as waiting for human action."""
        return self._mark_run_status(
            db, workflow_run_id=workflow_run_id, status="waiting_for_human"
        )

    def mark_run_completed(self, db: Session, *, workflow_run_id: uuid.UUID) -> WorkflowRun:
        """Mark a workflow run as completed."""
        run = self._mark_run_status(db, workflow_run_id=workflow_run_id, status="completed")
        run.completed_at = datetime.now(UTC)
        db.flush()
        return run

    def mark_run_failed(self, db: Session, *, workflow_run_id: uuid.UUID) -> WorkflowRun:
        """Mark a workflow run as failed."""
        run = self._mark_run_status(db, workflow_run_id=workflow_run_id, status="failed")
        run.completed_at = datetime.now(UTC)
        db.flush()
        return run

    def mark_run_cancelled(self, db: Session, *, workflow_run_id: uuid.UUID) -> WorkflowRun:
        """Mark a workflow run as cancelled."""
        run = self._mark_run_status(db, workflow_run_id=workflow_run_id, status="cancelled")
        run.completed_at = datetime.now(UTC)
        db.flush()
        return run

    def start_step(
        self,
        db: Session,
        *,
        workflow_run_id: uuid.UUID,
        step_name: str,
        status: str = "running",
    ) -> WorkflowStepTrace:
        """Create a workflow step trace in pending or running state."""
        if status not in {"pending", "running"}:
            raise ValidationError("WorkflowStepTrace must start as pending or running.")
        self._get_run(db, workflow_run_id=workflow_run_id)
        step = WorkflowStepTrace(
            workflow_run_id=workflow_run_id,
            step_name=step_name,
            status=status,
            started_at=datetime.now(UTC) if status == "running" else None,
        )
        db.add(step)
        db.flush()
        return step

    def mark_step_completed(
        self,
        db: Session,
        *,
        workflow_step_trace_id: uuid.UUID,
    ) -> WorkflowStepTrace:
        """Mark a workflow step as completed."""
        step = self._get_step(db, workflow_step_trace_id=workflow_step_trace_id)
        step.status = "completed"
        step.completed_at = datetime.now(UTC)
        db.flush()
        return step

    def mark_step_failed(
        self,
        db: Session,
        *,
        workflow_step_trace_id: uuid.UUID,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> WorkflowStepTrace:
        """Mark a workflow step as failed with sanitized error details."""
        step = self._get_step(db, workflow_step_trace_id=workflow_step_trace_id)
        step.status = "failed"
        step.error_type = error_type
        step.error_message = error_message
        step.completed_at = datetime.now(UTC)
        db.flush()
        return step

    def mark_step_skipped(
        self,
        db: Session,
        *,
        workflow_step_trace_id: uuid.UUID,
    ) -> WorkflowStepTrace:
        """Mark a workflow step as skipped."""
        step = self._get_step(db, workflow_step_trace_id=workflow_step_trace_id)
        step.status = "skipped"
        step.completed_at = datetime.now(UTC)
        db.flush()
        return step

    def record_ai_trace(
        self,
        db: Session,
        *,
        workflow_step_trace_id: uuid.UUID,
        ai_component_name: str,
        status: str,
        provider: str | None = None,
        model_name: str | None = None,
        prompt_version: str | None = None,
        input_schema_version: str | None = None,
        output_schema_version: str | None = None,
        latency_ms: int | None = None,
        input_reference: dict[str, Any] | None = None,
        output_reference: dict[str, Any] | None = None,
        validation_error: dict[str, Any] | None = None,
        token_usage: dict[str, Any] | None = None,
    ) -> AITrace:
        """Persist AI call metadata without making an AI provider call."""
        self._get_step(db, workflow_step_trace_id=workflow_step_trace_id)
        trace = AITrace(
            workflow_step_trace_id=workflow_step_trace_id,
            ai_component_name=ai_component_name,
            provider=provider,
            model_name=model_name,
            prompt_version=prompt_version,
            input_schema_version=input_schema_version,
            output_schema_version=output_schema_version,
            status=status,
            latency_ms=latency_ms,
            input_reference=input_reference,
            output_reference=output_reference,
            validation_error=validation_error,
            token_usage=token_usage,
        )
        db.add(trace)
        db.flush()
        return trace

    def _get_run(self, db: Session, *, workflow_run_id: uuid.UUID) -> WorkflowRun:
        run = db.get(WorkflowRun, workflow_run_id)
        if run is None:
            raise NotFoundError("WorkflowRun was not found.")
        return run

    def _get_step(
        self,
        db: Session,
        *,
        workflow_step_trace_id: uuid.UUID,
    ) -> WorkflowStepTrace:
        step = db.get(WorkflowStepTrace, workflow_step_trace_id)
        if step is None:
            raise NotFoundError("WorkflowStepTrace was not found.")
        return step

    def _mark_run_status(
        self,
        db: Session,
        *,
        workflow_run_id: uuid.UUID,
        status: str,
    ) -> WorkflowRun:
        run = self._get_run(db, workflow_run_id=workflow_run_id)
        run.status = status
        db.flush()
        return run

    def _validate_related_entity(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        related_entity_type: str | None,
        related_entity_id: uuid.UUID | None,
    ) -> None:
        if related_entity_type is None and related_entity_id is None:
            return
        if related_entity_type is None or related_entity_id is None:
            raise ValidationError("Workflow related entity type and id must be supplied together.")

        if related_entity_type == "job":
            entity = db.get(Job, related_entity_id)
            entity_organization_id = entity.organization_id if entity is not None else None
        elif related_entity_type == "candidate":
            entity = db.get(Candidate, related_entity_id)
            entity_organization_id = entity.organization_id if entity is not None else None
        elif related_entity_type == "resume":
            entity = db.get(Resume, related_entity_id)
            entity_organization_id = (
                entity.candidate.organization_id if entity is not None else None
            )
        elif related_entity_type == "job_application":
            entity = db.get(JobApplication, related_entity_id)
            entity_organization_id = entity.organization_id if entity is not None else None
        elif related_entity_type == "job_profile":
            entity = db.get(JobProfile, related_entity_id)
            entity_organization_id = entity.job.organization_id if entity is not None else None
        elif related_entity_type == "candidate_profile":
            entity = db.get(CandidateProfile, related_entity_id)
            entity_organization_id = (
                entity.resume.candidate.organization_id if entity is not None else None
            )
        elif related_entity_type == "candidate_evaluation":
            entity = db.get(CandidateEvaluation, related_entity_id)
            entity_organization_id = (
                entity.job_application.organization_id if entity is not None else None
            )
        elif related_entity_type == "chat_thread":
            entity = db.get(ChatThread, related_entity_id)
            entity_organization_id = entity.organization_id if entity is not None else None
        else:
            raise ValidationError("Workflow related entity type is not supported.")

        if entity is None:
            raise NotFoundError("Workflow related entity was not found.")
        if entity_organization_id != organization_id:
            raise ValidationError("Workflow related entity belongs to a different organization.")
