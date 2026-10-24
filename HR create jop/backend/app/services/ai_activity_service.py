from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AITrace,
    Candidate,
    Job,
    JobApplication,
    Resume,
    WorkflowRun,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.observability_service import ObservabilityService

DEFAULT_RUN_LIMIT = 50

WORKFLOW_TITLES: dict[str, str] = {
    "candidate_evaluation": "Candidate Evaluation",
    "job_profile_extraction": "Job Profile Extraction",
    "candidate_profile_extraction": "Candidate Profile Extraction",
}

STEP_LABELS: dict[str, str] = {
    "evaluate_candidate": "Evaluate Candidate",
    "extract_job_profile": "Extract Job Profile",
    "extract_candidate_profile": "Extract Candidate Profile",
}

AI_COMPONENT_LABELS: dict[str, str] = {
    "match_evidence_generator": "Generate Match Evidence",
    "evaluation_explainer": "Generate Evaluation Explanation",
}


def _step_status_display(status: str) -> str:
    if status == "completed":
        return "success"
    if status in {"failed", "validation_failed"}:
        return "error"
    return "running"


def _run_status_display(status: str) -> str:
    if status == "completed":
        return "success"
    if status == "failed":
        return "error"
    return status


def _duration_ms(started_at: datetime | None, completed_at: datetime | None) -> int | None:
    if started_at is None or completed_at is None:
        return None
    return int((completed_at - started_at).total_seconds() * 1000)


class AIActivityService:
    """Read/retry layer over the workflow observability tables.

    Presents a practitioner-facing view of WorkflowRun/WorkflowStepTrace/AITrace
    records (list + stats) and re-runs a failed run's underlying workflow.
    """

    def __init__(self) -> None:
        self._observability = ObservabilityService()

    def list_runs(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        limit: int = DEFAULT_RUN_LIMIT,
    ) -> list[dict[str, Any]]:
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.organization_id == organization_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
        )
        runs = list(db.scalars(statement))
        return [self._run_view(db, run) for run in runs]

    def get_stats(self, db: Session, *, organization_id: uuid.UUID) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(hours=24)
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.organization_id == organization_id)
            .where(WorkflowRun.created_at >= since)
        )
        recent = list(db.scalars(statement))
        successful = sum(1 for run in recent if run.status == "completed")
        failed = sum(1 for run in recent if run.status == "failed")

        latency_ms: list[int] = []
        for run in recent:
            try:
                traces = self._observability.list_ai_traces(
                    db,
                    workflow_run_id=run.id,
                    organization_id=organization_id,
                )
            except (NotFoundError, ValidationError):
                continue
            latency_ms.extend(trace.latency_ms for trace in traces if trace.latency_ms is not None)
        avg_latency_ms = round(sum(latency_ms) / len(latency_ms)) if latency_ms else None
        return {
            "total_runs_24h": len(recent),
            "successful": successful,
            "failed": failed,
            "avg_latency_ms": avg_latency_ms,
        }

    def retry_run(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        workflow_run_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Re-run a failed workflow for its related entity."""
        run = db.get(WorkflowRun, workflow_run_id)
        if run is None:
            raise NotFoundError("WorkflowRun was not found.")
        if run.organization_id != organization_id:
            raise ValidationError("WorkflowRun belongs to a different organization.")
        if run.status != "failed":
            raise ValidationError("Only failed workflow runs can be retried.")
        if run.related_entity_id is None:
            raise ValidationError("WorkflowRun has no related entity to retry.")

        new_run_id = self._dispatch(
            db,
            workflow_type=run.workflow_type,
            related_entity_type=run.related_entity_type,
            related_entity_id=run.related_entity_id,
            organization_id=organization_id,
        )
        db.commit()
        return {"run_id": new_run_id, "status": "running"}

    def _dispatch(
        self,
        db: Session,
        *,
        workflow_type: str,
        related_entity_type: str | None,
        related_entity_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> uuid.UUID:
        if workflow_type == "candidate_evaluation":
            if related_entity_type != "job_application":
                raise ValidationError(
                    "Candidate evaluation retry requires a job_application related entity."
                )
            return _rerun_candidate_evaluation(
                db,
                application_id=related_entity_id,
                organization_id=organization_id,
            ).workflow_run_id
        if workflow_type == "job_profile_extraction":
            if related_entity_type != "job":
                raise ValidationError("Job profile extraction retry requires a job entity.")
            return _rerun_job_profile_extraction(
                db,
                job_id=related_entity_id,
                organization_id=organization_id,
            ).workflow_run_id
        if workflow_type == "candidate_profile_extraction":
            if related_entity_type != "resume":
                raise ValidationError(
                    "Candidate profile extraction retry requires a resume entity."
                )
            return _rerun_candidate_profile_extraction(
                db,
                resume_id=related_entity_id,
                organization_id=organization_id,
            ).workflow_run_id
        raise ValidationError(f"Retry is not supported for workflow type: {workflow_type}")

    def _run_view(self, db: Session, run: WorkflowRun) -> dict[str, Any]:
        steps = self._observability.list_workflow_steps(db, workflow_run_id=run.id)
        traces: list[AITrace] = []
        try:
            traces = self._observability.list_ai_traces(db, workflow_run_id=run.id)
        except (NotFoundError, ValidationError):
            traces = []

        candidate_name, job_title = self._entity_labels(db, run)
        provider = traces[0].provider if traces else None
        model = traces[0].model_name if traces else None
        schema_version = (
            traces[0].output_schema_version or traces[0].input_schema_version if traces else None
        )
        prompt_version = traces[0].prompt_version if traces else None

        step_views: list[dict[str, Any]] = []
        for step in steps:
            step_views.append(
                {
                    "name": STEP_LABELS.get(step.step_name, step.step_name),
                    "status": _step_status_display(step.status),
                    "duration_ms": _duration_ms(step.started_at, step.completed_at),
                }
            )
        for trace in traces:
            step_views.append(
                {
                    "name": AI_COMPONENT_LABELS.get(
                        trace.ai_component_name, trace.ai_component_name
                    ),
                    "status": _step_status_display(trace.status),
                    "duration_ms": trace.latency_ms,
                }
            )

        return {
            "id": run.id,
            "run_id": str(run.id),
            "workflow_type": run.workflow_type,
            "status": _run_status_display(run.status),
            "title": WORKFLOW_TITLES.get(run.workflow_type, run.workflow_type),
            "candidate_name": candidate_name,
            "job_title": job_title,
            "provider": provider or "—",
            "model": model or "—",
            "timestamp": run.started_at or run.created_at,
            "total_duration_ms": _duration_ms(run.started_at, run.completed_at),
            "steps": step_views,
            "schema_version": schema_version or "n/a",
            "prompt": prompt_version or "n/a",
        }

    @staticmethod
    def _entity_labels(db: Session, run: WorkflowRun) -> tuple[str | None, str | None]:
        entity_type = run.related_entity_type
        entity_id = run.related_entity_id
        if entity_type is None or entity_id is None:
            return None, None
        if entity_type == "job_application":
            application = db.get(JobApplication, entity_id)
            if application is None:
                return None, None
            candidate = application.candidate
            job = application.job
            return (
                candidate.full_name if candidate is not None else None,
                job.title if job is not None else None,
            )
        if entity_type == "job":
            job = db.get(Job, entity_id)
            return None, job.title if job is not None else None
        if entity_type in {"resume", "candidate_profile"}:
            resume = db.get(Resume, entity_id) if entity_type == "resume" else None
            if resume is None:
                return None, None
            candidate = db.get(Candidate, resume.candidate_id)
            return (
                candidate.full_name if candidate is not None else None,
                None,
            )
        if entity_type == "candidate":
            candidate = db.get(Candidate, entity_id)
            return (
                candidate.full_name if candidate is not None else None,
                None,
            )
        return None, None


def _rerun_candidate_evaluation(
    db: Session,
    *,
    application_id: uuid.UUID,
    organization_id: uuid.UUID,
):
    from app.ai.providers import get_provider
    from app.ai.workflows import CandidateEvaluationWorkflow
    from app.core.config import settings
    from app.models import JobApplication
    from app.services.errors import NotFoundError
    from app.services.job_profile_service import JobProfileService
    from app.services.job_service import JobService
    from app.services.resume_details_service import (
        derive_evidence_payload,
        derive_explanation_payload,
    )
    from app.services.resume_service import ResumeService

    application = db.get(JobApplication, application_id)
    if application is None:
        raise NotFoundError("JobApplication was not found.")
    if application.organization_id != organization_id:
        raise ValidationError("JobApplication belongs to a different organization.")
    job = JobService().get(db, job_id=application.job_id, organization_id=organization_id)
    approved_profile = None
    for profile in JobProfileService().list_versions(
        db, job_id=application.job_id, organization_id=organization_id
    ):
        if profile.status == "approved":
            approved_profile = profile
    requirements = (
        approved_profile.profile_data.get("requirements") if approved_profile is not None else []
    )
    resume = ResumeService().get(
        db,
        resume_id=application.resume_id,
        organization_id=organization_id,
    )
    resume_text = (resume.extracted_text or None) if resume is not None else None
    evidence_payload = derive_evidence_payload(
        resume_text=resume_text,
        requirements=requirements,
    )
    explanation_payload = derive_explanation_payload(
        job_title=job.title,
        requirements=requirements,
        evidence_payload=evidence_payload,
    )
    workflow = CandidateEvaluationWorkflow(
        evidence_provider=get_provider(
            settings,
            provider="fake",
            model="fake-evidence-model",
            structured_payload=evidence_payload,
        ),
        explanation_provider=get_provider(
            settings,
            provider="fake",
            model="fake-explanation-model",
            structured_payload=explanation_payload,
        ),
    )
    return workflow.run(
        db,
        job_application_id=application_id,
        organization_id=organization_id,
    )


def _rerun_job_profile_extraction(
    db: Session,
    *,
    job_id: uuid.UUID,
    organization_id: uuid.UUID,
):
    from app.ai.providers import get_provider
    from app.ai.providers.factory import resolve_ai_config
    from app.ai.workflows import JobProfileExtractionWorkflow
    from app.core.config import settings
    from app.services.job_service import JobService

    job = JobService().get(db, job_id=job_id, organization_id=organization_id)
    if not resolve_ai_config(settings)["is_fake"]:
        provider = get_provider(settings)
    else:
        provider = get_provider(
            settings,
            provider="fake",
            model="fake-model",
            structured_payload=_derive_job_profile_extraction_payload(job),
        )
    return JobProfileExtractionWorkflow(provider).run(
        db,
        job_id=job_id,
        organization_id=organization_id,
    )


def _derive_job_profile_extraction_payload(job) -> dict:
    """Deterministic JobProfileExtractionOutput payload grounded in the job.

    Fake-provider stand-in used by the retry path so a re-run produces a valid
    profile from the job's own title and declared requirement vocabulary
    instead of depending on a live provider call.
    """
    requirements: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in [*(job.required_skills or []), *(job.requirements or [])]:
        text = (value or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        requirements.append({"text": text, "category": "must_have", "dimension": "skill"})
    requirements.append(
        {
            "text": "Relevant professional experience",
            "category": "must_have",
            "dimension": "experience",
        }
    )
    return {
        "title": job.title,
        "summary": "Job profile derived from the job's own data.",
        "requirements": requirements,
    }


def _rerun_candidate_profile_extraction(
    db: Session,
    *,
    resume_id: uuid.UUID,
    organization_id: uuid.UUID,
):
    from app.ai.providers import get_provider
    from app.ai.workflows import CandidateProfileExtractionWorkflow
    from app.core.config import settings
    from app.models import Candidate
    from app.services.errors import NotFoundError
    from app.services.resume_details_service import derive_profile_payload
    from app.services.resume_service import ResumeService

    resume = ResumeService().get(db, resume_id=resume_id, organization_id=organization_id)
    if resume is None:
        raise NotFoundError("Resume was not found.")
    candidate = db.get(Candidate, resume.candidate_id)
    full_name = (
        candidate.full_name
        if candidate is not None and candidate.full_name
        else "Extracted Candidate"
    )
    resume_text = resume.extracted_text or ""
    provider = get_provider(
        settings,
        provider="fake",
        model="fake-model",
        structured_payload=derive_profile_payload(
            full_name=full_name,
            resume_text=resume_text,
        ),
    )
    return CandidateProfileExtractionWorkflow(provider).run(
        db,
        resume_id=resume_id,
        organization_id=organization_id,
        resume_text=resume_text,
    )
