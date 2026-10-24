"""Job profile extraction workflow (Phase 3.4).

Orchestrates a single deterministic run for a Job: load the job and validate that
it has a ``raw_description``, call the AI provider for structured job-profile
data, validate that data against the extraction contract, and persist a new
JobProfile version via the ``JobProfileService``. Every phase is recorded through
the ``WorkflowTraceService`` (workflow run, step trace, and AI trace).

The workflow never commits; the caller owns the transaction, so any failure rolls
back safely. Only the provider-agnostic ``AIProvider`` interface is consumed;
real provider adapters, LangChain/LangGraph/agents, workers, and async execution
are out of scope.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.contracts import (
    JOB_PROFILE_EXTRACTION_SCHEMA_VERSION,
    JobProfileExtractionOutput,
    validate_job_profile_extraction,
)
from app.ai.markers import wrap_untrusted
from app.ai.providers.base import AIProvider, StructuredGenerationRequest
from app.ai.providers.errors import ProviderError
from app.models import Job
from app.services.errors import NotFoundError, ValidationError
from app.services.job_profile_service import JobProfileService
from app.services.workflow_trace_service import WorkflowTraceService

WORKFLOW_TYPE = "job_profile_extraction"
STEP_NAME = "extract_job_profile"
AI_COMPONENT_NAME = "job_profile_extractor"
PROMPT_VERSION = "2"


def _sha256(value: str) -> str:
    """Return the hex SHA-256 digest of a string value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _serialize_output(profile_data: dict) -> str:
    """Serialize the verified persisted output deterministically for hashing."""
    return json.dumps(profile_data, sort_keys=True, default=str)


def _verified_quality_review(
    extracted: JobProfileExtractionOutput,
    raw_description: str,
) -> dict[str, object]:
    """Persist only quality findings that quote the source description exactly."""
    review = extracted.quality_review
    if review is None:
        return {"status": "unavailable", "findings": []}

    findings = [
        finding.model_dump()
        for finding in review.findings
        if finding.source_quote in raw_description
    ]
    status = "verified" if len(findings) == len(review.findings) else "partially_verified"
    return {"status": status, "findings": findings}


@dataclass(frozen=True)
class JobProfileExtractionResult:
    """Outcome of a successful job profile extraction run."""

    profile_id: uuid.UUID
    workflow_run_id: uuid.UUID
    workflow_step_trace_id: uuid.UUID
    ai_trace_id: uuid.UUID
    version_number: int


class JobProfileExtractionWorkflow:
    """Orchestrate a single job profile extraction run."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        trace_service: WorkflowTraceService | None = None,
        profile_service: JobProfileService | None = None,
    ) -> None:
        self._provider = provider
        self._trace_service = trace_service or WorkflowTraceService()
        self._profile_service = profile_service or JobProfileService()

    def run(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> JobProfileExtractionResult:
        """Execute the extraction run, raising on any failure."""
        job = self._get_job(db, job_id=job_id, organization_id=organization_id)
        raw_description = self._require_raw_description(job)

        run = self._trace_service.start_run(
            db,
            organization_id=organization_id,
            workflow_type=WORKFLOW_TYPE,
            related_entity_type="job",
            related_entity_id=job.id,
            status="running",
        )
        step = self._trace_service.start_step(
            db,
            workflow_run_id=run.id,
            step_name=STEP_NAME,
            status="running",
        )
        input_reference = {
            "entity": "job",
            "entity_id": str(job.id),
            "raw_description_sha256": _sha256(raw_description),
        }

        try:
            result = self._provider.generate_structured(
                StructuredGenerationRequest(
                    input=json.dumps(
                        {
                            "trusted_task_instructions": (
                                "Extract the job profile from the source description. Also review "
                                "the description for unclear requirements, possible conflicts, "
                                "unclear priority between essential and optional criteria, and "
                                "requirements that are not measurable. Do not add, rewrite, or "
                                "infer requirements. Each quality finding must include an exact "
                                "verbatim source_quote, a concise concern, and a question for HR "
                                "to review. An empty findings list is valid when no clear issue "
                                "is present. These suggestions are advisory and never alter the "
                                "extracted requirements or approve the profile."
                            ),
                            "job_description_source": wrap_untrusted(
                                raw_description, "JOB_DESCRIPTION"
                            ),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    output_schema=JobProfileExtractionOutput,
                    schema_version=JOB_PROFILE_EXTRACTION_SCHEMA_VERSION,
                    metadata={"workflow": WORKFLOW_TYPE},
                )
            )
        except ProviderError as error:
            self._record_failure_trace(db, step.id, input_reference)
            self._trace_service.mark_step_failed(
                db,
                workflow_step_trace_id=step.id,
                error_type=type(error).__name__,
                error_message=str(error),
            )
            self._trace_service.mark_run_failed(db, workflow_run_id=run.id)
            raise

        try:
            extracted = validate_job_profile_extraction(result.data)
        except ValidationError as error:
            self._trace_service.record_ai_trace(
                db,
                workflow_step_trace_id=step.id,
                ai_component_name=AI_COMPONENT_NAME,
                status="validation_failed",
                provider=result.provider,
                model_name=result.model,
                prompt_version=PROMPT_VERSION,
                input_schema_version=JOB_PROFILE_EXTRACTION_SCHEMA_VERSION,
                output_schema_version=result.schema_version,
                latency_ms=result.latency_ms,
                input_reference=input_reference,
                validation_error={"schema": result.schema_version, "message": str(error)},
            )
            self._trace_service.mark_step_failed(
                db,
                workflow_step_trace_id=step.id,
                error_type="ValidationError",
                error_message=str(error),
            )
            self._trace_service.mark_run_failed(db, workflow_run_id=run.id)
            raise

        profile_data = extracted.model_dump(exclude={"quality_review"})
        profile_data["quality_review"] = _verified_quality_review(extracted, raw_description)
        output_reference = {"output_sha256": _sha256(_serialize_output(profile_data))}
        ai_trace = self._trace_service.record_ai_trace(
            db,
            workflow_step_trace_id=step.id,
            ai_component_name=AI_COMPONENT_NAME,
            status="succeeded",
            provider=result.provider,
            model_name=result.model,
            prompt_version=PROMPT_VERSION,
            input_schema_version=JOB_PROFILE_EXTRACTION_SCHEMA_VERSION,
            output_schema_version=result.schema_version,
            latency_ms=result.latency_ms,
            input_reference=input_reference,
            output_reference=output_reference,
            token_usage=result.token_usage,
        )

        make_current = not self._has_approved_profile(db, job)
        profile = self._profile_service.create_version(
            db,
            job_id=job.id,
            status="draft",
            source="ai_extracted",
            profile_data=profile_data,
            raw_input_snapshot=input_reference,
            provenance={
                "workflow": WORKFLOW_TYPE,
                "provider": result.provider,
                "model": result.model,
            },
            organization_id=organization_id,
            make_current=make_current,
        )

        self._trace_service.mark_step_completed(db, workflow_step_trace_id=step.id)
        self._trace_service.mark_run_completed(db, workflow_run_id=run.id)

        return JobProfileExtractionResult(
            profile_id=profile.id,
            workflow_run_id=run.id,
            workflow_step_trace_id=step.id,
            ai_trace_id=ai_trace.id,
            version_number=profile.version_number,
        )

    def _get_job(self, db: Session, *, job_id: uuid.UUID, organization_id: uuid.UUID) -> Job:
        job = db.get(Job, job_id)
        if job is None:
            raise ValidationError("Job was not found.")
        if job.organization_id != organization_id:
            raise ValidationError("Job belongs to a different organization.")
        return job

    @staticmethod
    def _require_raw_description(job: Job) -> str:
        if not job.raw_description:
            raise ValidationError("Job has no raw description to extract from.")
        return job.raw_description

    def _has_approved_profile(self, db: Session, job: Job) -> bool:
        versions = self._profile_service.list_versions(db, job_id=job.id)
        return any(profile.status == "approved" for profile in versions)

    def _record_failure_trace(
        self,
        db: Session,
        step_id: uuid.UUID,
        input_reference: dict[str, str],
    ) -> None:
        self._trace_service.record_ai_trace(
            db,
            workflow_step_trace_id=step_id,
            ai_component_name=AI_COMPONENT_NAME,
            status="failed",
            prompt_version=PROMPT_VERSION,
            input_schema_version=JOB_PROFILE_EXTRACTION_SCHEMA_VERSION,
            output_schema_version=JOB_PROFILE_EXTRACTION_SCHEMA_VERSION,
            input_reference=input_reference,
        )
