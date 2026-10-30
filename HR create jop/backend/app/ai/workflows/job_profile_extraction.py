"""Job profile extraction workflow (Phase 3.4).

Orchestrates a single deterministic run for a Job: gather manual description,
uploaded source text, and structured specifications, call the AI provider for
structured job-profile data, validate and source-check the output, and persist a
new draft JobProfile version. Every phase is recorded through the
``WorkflowTraceService`` (workflow run, step trace, and AI trace).

The workflow never commits; the caller owns the transaction, so any failure rolls
back safely. Only the provider-agnostic ``AIProvider`` interface is consumed;
real provider adapters, LangChain/LangGraph/agents, workers, and async execution
are out of scope.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.contracts import (
    JOB_PROFILE_EXTRACTION_SCHEMA_VERSION,
    JobProfileExtractionOutput,
    validate_job_profile_extraction,
)
from app.ai.markers import wrap_untrusted
from app.ai.providers.base import AIProvider, StructuredGenerationRequest
from app.ai.providers.errors import ProviderError
from app.models import Job, JobProfile
from app.services.errors import ValidationError
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


def _detect_specification_conflicts(
    job: Job, description_sources: dict[str, str]
) -> list[dict[str, object]]:
    """Report only conflicts backed by explicit structured and text values."""
    conflicts: list[dict[str, object]] = []
    employment_terms = {
        "full-time": ("full-time", "full time", "permanent"),
        "part-time": ("part-time", "part time"),
        "contract": ("contract", "contractor", "freelance"),
        "internship": ("internship", "intern"),
    }
    specified_type = (job.job_type or "").strip().lower()
    normalized_type = next(
        (label for label, terms in employment_terms.items() if specified_type in terms),
        specified_type,
    )
    source_type_values = []
    for source, text in description_sources.items():
        lowered = text.lower()
        for label, terms in employment_terms.items():
            matched_term = next((term for term in terms if term in lowered), None)
            if matched_term and label != normalized_type:
                match = re.search(re.escape(matched_term), text, re.I)
                source_type_values.append(
                    {
                        "value": label,
                        "source": source,
                        "source_quote": match.group(0) if match else matched_term,
                    }
                )
    if normalized_type and source_type_values:
        conflicts.append(
            {
                "field": "employment_type",
                "values": [
                    {"value": job.job_type, "source": "structured_specification"},
                    *source_type_values,
                ],
                "status": "unresolved",
            }
        )

    specified_experience = (job.experience or "").strip()
    specified_years = re.search(r"\d+(?:\.\d+)?", specified_experience)
    structured_year_value = float(specified_years.group(0)) if specified_years else None
    text_experience_values = []
    for source, text in description_sources.items():
        for match in re.finditer(r"\b\d+(?:\.\d+)?\+?\s*(?:years?|yrs?)\b", text, re.I):
            number = re.search(r"\d+(?:\.\d+)?", match.group(0))
            text_year_value = float(number.group(0)) if number else None
            if text_year_value != structured_year_value:
                text_experience_values.append(
                    {
                        "value": match.group(0),
                        "source": source,
                        "source_quote": match.group(0),
                    }
                )
    if specified_experience and text_experience_values:
        conflicts.append(
            {
                "field": "experience",
                "values": [
                    {"value": specified_experience, "source": "structured_specification"},
                    *text_experience_values,
                ],
                "status": "unresolved",
            }
        )
    return conflicts


def _verified_quality_review(
    extracted: JobProfileExtractionOutput,
    source_text: str,
) -> dict[str, object]:
    """Persist only quality findings that quote the source description exactly."""
    review = extracted.quality_review
    if review is None:
        return {"status": "unavailable", "findings": []}

    findings = [
        finding.model_dump() for finding in review.findings if finding.source_quote in source_text
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
        request_key: str | None = None,
    ) -> JobProfileExtractionResult:
        """Execute the extraction run, raising on any failure."""
        job = self._get_job(db, job_id=job_id, organization_id=organization_id)
        original_listing_text = self._source_listing_text(db, job)
        raw_description = original_listing_text or self._require_raw_description(job)
        if request_key:
            existing = db.scalar(
                select(JobProfile).where(
                    JobProfile.job_id == job.id,
                    JobProfile.request_key == request_key,
                )
            )
            if existing is not None:
                provenance = existing.provenance or {}
                return JobProfileExtractionResult(
                    profile_id=existing.id,
                    workflow_run_id=uuid.UUID(provenance["workflow_run_id"]),
                    workflow_step_trace_id=uuid.UUID(provenance["workflow_step_trace_id"]),
                    ai_trace_id=uuid.UUID(provenance["ai_trace_id"]),
                    version_number=existing.version_number,
                )
        source_texts = {
            "manual_description": (
                job.description_text
                if job.description_text is not None
                else raw_description
            ),
            "uploaded_file": job.source_file_text or "",
        }
        specifications = {
            "job_title": job.title,
            "department": job.department,
            "location": job.location,
            "employment_type": job.job_type,
            "required_experience": job.experience,
            "requirements": job.requirements or [],
            "required_skills": job.required_skills or [],
        }
        if not any(source_texts.values()) and not any(
            value for key, value in specifications.items() if key != "job_title" and value
        ):
            raise ValidationError(
                "Add a description, supported specifications, or a readable job file "
                "before extraction."
            )
        source_texts["structured_specification"] = json.dumps(
            specifications, ensure_ascii=False, sort_keys=True
        )
        combined_sources = "\n".join(source_texts.values())

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
            "manual_description_sha256": _sha256(source_texts["manual_description"]),
            "uploaded_file_sha256": job.source_file_sha256,
            "structured_specifications_sha256": _sha256(source_texts["structured_specification"]),
        }

        try:
            result = self._provider.generate_structured(
                StructuredGenerationRequest(
                    input=json.dumps(
                        {
                            "trusted_task_instructions": (
                                "Extract only requirements supported by the supplied job sources. "
                                "Classify requirements as must_have, important, or nice_to_have, "
                                "and as skill, experience, education, certification, "
                                "or responsibility. "
                                "Include source and an exact source_quote for every requirement. "
                                "Use source=manual_description for manually entered description, "
                                "uploaded_file for the uploaded file text, and "
                                "structured_specification for supplied structured fields. Do not "
                                "invent missing requirements; omit unsupported details. "
                                "Also review "
                                "the description for unclear requirements, possible conflicts, "
                                "unclear priority between essential and optional criteria, and "
                                "requirements that are not measurable. Do not add, rewrite, or "
                                "infer requirements. Each quality finding must include an exact "
                                "verbatim source_quote, a concise concern, and a question for HR "
                                "to review. An empty findings list is valid when no clear issue "
                                "is present. These suggestions are advisory and never alter the "
                                "extracted requirements or approve the profile."
                            ),
                            "manual_description_source": wrap_untrusted(
                                source_texts["manual_description"], "MANUAL_DESCRIPTION"
                            ),
                            "uploaded_file_source": wrap_untrusted(
                                source_texts["uploaded_file"], "UPLOADED_JOB_FILE"
                            ),
                            "structured_specifications_source": wrap_untrusted(
                                source_texts["structured_specification"],
                                "STRUCTURED_SPECIFICATIONS",
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

        requirements = []
        for requirement in extracted.requirements:
            item = requirement.model_dump(exclude_none=True)
            evidence_source = item.get("source")
            quote = item.get("source_quote")
            source_content = source_texts.get(evidence_source or "", "")
            if quote and source_content and quote in source_content:
                item["evidence_status"] = "verified"
            else:
                item.pop("source", None)
                item.pop("source_quote", None)
                item["evidence_status"] = "uncertain"
            requirements.append(item)
        profile_data = extracted.model_dump(exclude={"quality_review", "requirements"})
        profile_data["requirements"] = requirements
        profile_data["quality_review"] = _verified_quality_review(extracted, combined_sources)
        dimensions = ("skill", "experience", "education", "certification", "responsibility")
        coverage = {}
        for dimension in dimensions:
            matching = [item for item in requirements if item["dimension"] == dimension]
            if dimension == "experience" and job.experience:
                coverage[dimension] = "provided"
            elif any(item.get("evidence_status") == "verified" for item in matching):
                coverage[dimension] = "provided"
            elif matching:
                coverage[dimension] = "uncertain"
            else:
                coverage[dimension] = "unspecified"
        profile_data["coverage"] = coverage
        profile_data["conflicts"] = _detect_specification_conflicts(
            job,
            {
                "manual_description": source_texts["manual_description"],
                "uploaded_file": source_texts["uploaded_file"],
            },
        )
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
        previous_profile = self._profile_service.get_current_or_latest(db, job_id=job.id)
        previous_provenance = previous_profile.provenance or {} if previous_profile else {}
        inherited = {
            key: previous_provenance[key]
            for key in ("source", "field_origins")
            if key in previous_provenance
        }
        raw_input_snapshot = dict(input_reference)
        if original_listing_text is not None:
            raw_input_snapshot["original_listing_text"] = original_listing_text
        profile = self._profile_service.create_version(
            db,
            job_id=job.id,
            status="draft",
            source="ai_extracted",
            profile_data=profile_data,
            raw_input_snapshot=raw_input_snapshot,
            provenance={
                **inherited,
                "workflow": WORKFLOW_TYPE,
                "provider": result.provider,
                "model": result.model,
                "workflow_run_id": str(run.id),
                "workflow_step_trace_id": str(step.id),
                "ai_trace_id": str(ai_trace.id),
            },
            organization_id=organization_id,
            make_current=make_current,
            request_key=request_key,
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
        """Kept for compatibility with consumers that validate description inputs."""
        if not job.raw_description:
            raise ValidationError("Job has no raw description to extract from.")
        return job.raw_description

    def _source_listing_text(self, db: Session, job: Job) -> str | None:
        profile = self._profile_service.get_current_or_latest(db, job_id=job.id)
        if profile is None or not isinstance(profile.raw_input_snapshot, dict):
            return None
        text = profile.raw_input_snapshot.get("original_listing_text")
        return text if isinstance(text, str) and text.strip() else None

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
