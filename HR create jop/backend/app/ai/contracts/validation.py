"""Validation helpers for structured AI output contracts.

Each helper accepts structured Python data, validates it through Pydantic, and
returns the validated contract instance. On failure a Pydantic ``ValidationError``
is translated into the Phase 3.1 application ``ValidationError`` so callers can
rely on a single error hierarchy. These helpers never persist anything and never
call an external provider.
"""

from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.ai.contracts.candidate_profile import CandidateProfileExtractionOutput
from app.ai.contracts.evaluation import EvaluationExplanationOutput
from app.ai.contracts.job_draft import JobDraftSuggestionOutput
from app.ai.contracts.job_profile import JobProfileExtractionOutput, JobRequirement
from app.ai.contracts.match_evidence import MatchEvidenceListOutput, MatchEvidenceOutput
from app.services.errors import ValidationError

T = TypeVar("T", bound=BaseModel)


def _validate_contract(contract_type: type[T], data: Any) -> T:
    try:
        return contract_type.model_validate(data)
    except PydanticValidationError as error:
        raise ValidationError(f"Invalid AI output contract: {error}") from error


def validate_job_profile_extraction(data: Any) -> JobProfileExtractionOutput:
    """Validate raw extraction data into a JobProfileExtractionOutput."""
    return _validate_contract(JobProfileExtractionOutput, data)


def validate_job_draft_suggestion(data: Any) -> JobDraftSuggestionOutput:
    """Validate raw suggestion data into a JobDraftSuggestionOutput."""
    return _validate_contract(JobDraftSuggestionOutput, data)


def normalize_job_profile_requirements(value: Any) -> list[JobRequirement]:
    """Normalize persisted job profile ``requirements`` into canonical form.

    Read-path compatibility helper for anything consuming a JobProfile's
    ``profile_data``. Accepts the v1.0 flat ``list[str]`` shape (legacy rows)
    or the canonical v1.1 structured shape and returns a list of
    ``JobRequirement`` instances with system-generated keys. Flat legacy
    entries get ``category="important"`` and ``dimension="skill"`` defaults
    applied at read time only. Mixed shapes, unsupported items, and duplicate
    keys are rejected with the shared application ``ValidationError``.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError("Job profile requirements must be a list.")
    has_flat = any(isinstance(item, str) for item in value)
    has_structured = any(isinstance(item, dict) for item in value)
    if has_flat and has_structured:
        raise ValidationError(
            "Job profile requirements must not mix v1.0 strings and v1.1 structures."
        )
    try:
        if has_flat:
            if any(not isinstance(item, str) for item in value):
                raise ValidationError("Job profile requirements contain unsupported items.")
            requirements = [
                JobRequirement(text=item, category="important", dimension="skill") for item in value
            ]
        else:
            if any(not isinstance(item, dict) for item in value):
                raise ValidationError("Job profile requirements contain unsupported items.")
            requirements = [JobRequirement.model_validate(item) for item in value]
    except PydanticValidationError as error:
        raise ValidationError(f"Invalid persisted job profile requirements: {error}") from error

    seen: set[str] = set()
    for requirement in requirements:
        if requirement.key in seen:
            raise ValidationError(
                f"Duplicate requirement key {requirement.key!r} in persisted job profile."
            )
        seen.add(requirement.key)
    return requirements


def validate_candidate_profile_extraction(data: Any) -> CandidateProfileExtractionOutput:
    """Validate raw extraction data into a CandidateProfileExtractionOutput."""
    return _validate_contract(CandidateProfileExtractionOutput, data)


def validate_match_evidence(data: Any) -> MatchEvidenceOutput:
    """Validate raw extraction data into a MatchEvidenceOutput."""
    return _validate_contract(MatchEvidenceOutput, data)


def validate_match_evidence_list(data: Any, *, allowed_keys: set[str]) -> MatchEvidenceListOutput:
    """Validate raw data into a MatchEvidenceListOutput bound to allowed requirement keys.

    In addition to Pydantic shape validation (including the mandatory
    ``requirement_key`` pattern and duplicate rejection), every
    ``requirement_key`` returned by the producer must exist in ``allowed_keys``
    — the exact requirement-key set supplied to the producer. An element whose
    key is absent from ``allowed_keys`` (or an empty key set when evidence is
    required) is rejected, matching the schema v1.2 contract boundary.
    """
    try:
        output = _validate_contract(MatchEvidenceListOutput, data)
    except ValidationError as error:
        raise ValidationError(f"Invalid AI output contract: {error}") from error
    for item in output.evidence_items:
        key = item.requirement_ref["requirement_key"]
        if key not in allowed_keys:
            raise ValidationError(
                f"Match evidence requirement_key {key!r} was not among the "
                "requirement keys supplied to the AI."
            )
    return output


def validate_evaluation_explanation(data: Any) -> EvaluationExplanationOutput:
    """Validate raw extraction data into an EvaluationExplanationOutput."""
    return _validate_contract(EvaluationExplanationOutput, data)
