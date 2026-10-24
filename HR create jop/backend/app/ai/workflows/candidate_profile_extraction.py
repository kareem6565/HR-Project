"""Candidate profile extraction workflow (Phase 3.5).

Orchestrates a single deterministic run for a Resume: load the resume and
validate that it exists and belongs to the expected organization, require an
explicit ``resume_text`` input, call the AI provider for structured candidate
profile data, validate that data against the extraction contract, and persist a
new CandidateProfile version via the ``CandidateProfileService``. Every phase is
recorded through the ``WorkflowTraceService`` (workflow run, step trace, and AI
trace).

The Resume is the immutable source document; the CandidateProfile is a versioned
generated artifact. Reprocessing the same resume creates a new version and never
overwrites or deletes prior versions.

The workflow never commits; the caller owns the transaction, so any failure
rolls back safely. Only the provider-agnostic ``AIProvider`` interface is
consumed; real provider adapters, LangChain/LangGraph/agents, resume parsing,
workers, and async execution are out of scope. Candidate profile extraction
produces structured evidence only and never creates an HR decision, score, match
evidence, or candidate evaluation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.contracts import (
    AI_CONTRACT_SCHEMA_VERSION,
    CandidateProfileExtractionOutput,
    validate_candidate_profile_extraction,
)
from app.ai.markers import wrap_untrusted
from app.ai.providers.base import AIProvider, StructuredGenerationRequest
from app.ai.providers.errors import ProviderError
from app.models import Resume
from app.services.candidate_profile_service import CandidateProfileService
from app.services.errors import NotFoundError, ValidationError
from app.services.workflow_trace_service import WorkflowTraceService

WORKFLOW_TYPE = "candidate_profile_extraction"
STEP_NAME = "extract_candidate_profile"
AI_COMPONENT_NAME = "candidate_profile_extractor"
PROMPT_VERSION = "1"


def _sha256(value: str) -> str:
    """Return the hex SHA-256 digest of a string value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _serialize_output(extracted: CandidateProfileExtractionOutput) -> str:
    """Serialize validated output deterministically for hashing."""
    return json.dumps(extracted.model_dump(), sort_keys=True, default=str)


@dataclass(frozen=True)
class CandidateProfileExtractionPayload:
    """In-memory generated candidate profile data before database persistence."""

    extracted: CandidateProfileExtractionOutput
    provider_result: Any
    input_reference: dict[str, str]


@dataclass(frozen=True)
class CandidateProfileExtractionResult:
    """Outcome of a successful candidate profile extraction run."""

    profile_id: uuid.UUID
    workflow_run_id: uuid.UUID
    workflow_step_trace_id: uuid.UUID
    ai_trace_id: uuid.UUID
    version_number: int


class CandidateProfileExtractionWorkflow:
    """Orchestrate a single candidate profile extraction run."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        trace_service: WorkflowTraceService | None = None,
        profile_service: CandidateProfileService | None = None,
    ) -> None:
        self._provider = provider
        self._trace_service = trace_service or WorkflowTraceService()
        self._profile_service = profile_service or CandidateProfileService()

    def generate(
        self,
        *,
        resume_text: str,
        resume_id: uuid.UUID | None = None,
    ) -> CandidateProfileExtractionPayload:
        """Extract structured profile data via AI provider without holding database transactions."""
        self._require_resume_text(resume_text)
        input_reference = {
            "entity": "resume",
            "entity_id": str(resume_id or ""),
            "resume_text_sha256": _sha256(resume_text),
        }

        result = self._provider.generate_structured(
            StructuredGenerationRequest(
                input=wrap_untrusted(resume_text, "CV"),
                output_schema=CandidateProfileExtractionOutput,
                schema_version=AI_CONTRACT_SCHEMA_VERSION,
                metadata={"workflow": WORKFLOW_TYPE},
            )
        )
        extracted = validate_candidate_profile_extraction(result.data)
        return CandidateProfileExtractionPayload(
            extracted=extracted,
            provider_result=result,
            input_reference=input_reference,
        )

    def persist(
        self,
        db: Session,
        *,
        resume_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: CandidateProfileExtractionPayload,
    ) -> CandidateProfileExtractionResult:
        """Persist generated candidate profile and workflow traces in a short transaction."""
        resume = self._get_resume(db, resume_id=resume_id, organization_id=organization_id)
        input_reference = payload.input_reference or {
            "entity": "resume",
            "entity_id": str(resume.id),
        }

        run = self._trace_service.start_run(
            db,
            organization_id=organization_id,
            workflow_type=WORKFLOW_TYPE,
            related_entity_type="resume",
            related_entity_id=resume.id,
            status="running",
        )
        step = self._trace_service.start_step(
            db,
            workflow_run_id=run.id,
            step_name=STEP_NAME,
            status="running",
        )

        output_reference = {"output_sha256": _sha256(_serialize_output(payload.extracted))}
        ai_trace = self._trace_service.record_ai_trace(
            db,
            workflow_step_trace_id=step.id,
            ai_component_name=AI_COMPONENT_NAME,
            status="succeeded",
            provider=payload.provider_result.provider,
            model_name=payload.provider_result.model,
            prompt_version=PROMPT_VERSION,
            input_schema_version=AI_CONTRACT_SCHEMA_VERSION,
            output_schema_version=payload.provider_result.schema_version,
            latency_ms=payload.provider_result.latency_ms,
            input_reference=input_reference,
            output_reference=output_reference,
            token_usage=payload.provider_result.token_usage,
        )

        profile = self._profile_service.create_version(
            db,
            resume_id=resume.id,
            status="extracted",
            source="ai_extracted",
            profile_data=payload.extracted.model_dump(),
            provenance={
                "workflow": WORKFLOW_TYPE,
                "provider": payload.provider_result.provider,
                "model": payload.provider_result.model,
                "schema_version": payload.provider_result.schema_version or AI_CONTRACT_SCHEMA_VERSION,
            },
            organization_id=organization_id,
            make_current=True,
        )

        self._trace_service.mark_step_completed(db, workflow_step_trace_id=step.id)
        self._trace_service.mark_run_completed(db, workflow_run_id=run.id)

        return CandidateProfileExtractionResult(
            profile_id=profile.id,
            workflow_run_id=run.id,
            workflow_step_trace_id=step.id,
            ai_trace_id=ai_trace.id,
            version_number=profile.version_number,
        )

    def run(
        self,
        db: Session,
        *,
        resume_id: uuid.UUID,
        organization_id: uuid.UUID,
        resume_text: str,
    ) -> CandidateProfileExtractionResult:
        """Execute extraction run by composing generate() outside DB transactions and persist()."""
        resume = self._get_resume(db, resume_id=resume_id, organization_id=organization_id)
        self._require_resume_text(resume_text)
        input_reference = {
            "entity": "resume",
            "entity_id": str(resume.id),
            "resume_text_sha256": _sha256(resume_text),
        }

        try:
            payload = self.generate(resume_text=resume_text, resume_id=resume.id)
        except ProviderError as error:
            run = self._trace_service.start_run(
                db,
                organization_id=organization_id,
                workflow_type=WORKFLOW_TYPE,
                related_entity_type="resume",
                related_entity_id=resume.id,
                status="running",
            )
            step = self._trace_service.start_step(
                db,
                workflow_run_id=run.id,
                step_name=STEP_NAME,
                status="running",
            )
            self._record_failure_trace(db, step.id, input_reference)
            self._trace_service.mark_step_failed(
                db,
                workflow_step_trace_id=step.id,
                error_type=type(error).__name__,
                error_message=str(error),
            )
            self._trace_service.mark_run_failed(db, workflow_run_id=run.id)
            raise
        except ValidationError as error:
            run = self._trace_service.start_run(
                db,
                organization_id=organization_id,
                workflow_type=WORKFLOW_TYPE,
                related_entity_type="resume",
                related_entity_id=resume.id,
                status="running",
            )
            step = self._trace_service.start_step(
                db,
                workflow_run_id=run.id,
                step_name=STEP_NAME,
                status="running",
            )
            self._trace_service.record_ai_trace(
                db,
                workflow_step_trace_id=step.id,
                ai_component_name=AI_COMPONENT_NAME,
                status="validation_failed",
                prompt_version=PROMPT_VERSION,
                input_schema_version=AI_CONTRACT_SCHEMA_VERSION,
                input_reference=input_reference,
                validation_error={"message": str(error)},
            )
            self._trace_service.mark_step_failed(
                db,
                workflow_step_trace_id=step.id,
                error_type="ValidationError",
                error_message=str(error),
            )
            self._trace_service.mark_run_failed(db, workflow_run_id=run.id)
            raise

        return self.persist(
            db,
            resume_id=resume.id,
            organization_id=organization_id,
            payload=payload,
        )

    def _get_resume(
        self, db: Session, *, resume_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Resume:
        resume = db.get(Resume, resume_id)
        if resume is None:
            raise ValidationError("Resume was not found.")
        if resume.candidate.organization_id != organization_id:
            raise ValidationError("Resume belongs to a different organization.")
        return resume

    @staticmethod
    def _require_resume_text(resume_text: str) -> None:
        if not isinstance(resume_text, str) or not resume_text.strip():
            raise ValidationError("Resume text is required for extraction.")

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
            input_schema_version=AI_CONTRACT_SCHEMA_VERSION,
            output_schema_version=AI_CONTRACT_SCHEMA_VERSION,
            input_reference=input_reference,
        )
