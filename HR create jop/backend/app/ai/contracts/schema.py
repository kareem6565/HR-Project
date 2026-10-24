"""Schema versioning for structured AI output contracts.

The initial contract schema version is ``1.0``; Phase 4.1 introduced ``1.1``
for the structured job requirement vocabulary. Every structured output
contract declares a ``schema_version`` that must be one of the supported
versions below. This boundary lets producers signal which contract revision
they conformed to, and lets consumers reject unrecognized revisions up front.
"""

from typing import Annotated

from pydantic import BeforeValidator, ValidationInfo

AI_CONTRACT_SCHEMA_VERSION = "1.1"
JOB_PROFILE_EXTRACTION_SCHEMA_VERSION = "1.2"
INTERVIEW_QUESTION_SCHEMA_VERSION = "1.2"

# Phase 4.2 introduced ``1.2`` for the structured per-requirement match evidence
# contract, which requires a ``requirement_ref`` carrying a ``requirement_key``
# that must reference an exact job requirement key supplied to the producer.
EVIDENCE_CONTRACT_SCHEMA_VERSION = "1.2"

SUPPORTED_SCHEMA_VERSIONS = frozenset(
    {
        "1.0",
        AI_CONTRACT_SCHEMA_VERSION,
        JOB_PROFILE_EXTRACTION_SCHEMA_VERSION,
        INTERVIEW_QUESTION_SCHEMA_VERSION,
    }
)


def validate_schema_version(value: object, _info: ValidationInfo) -> str:
    """Ensure a schema version is a non-empty string in a known revision.

    Tolerates a leading ``v`` prefix that some LLM producers emit (e.g. ``"v1.1"``)
    and returns the canonical ``"1.1"``.
    """
    if not isinstance(value, str):
        raise ValueError("schema_version must be a string.")
    version = value.strip()
    if not version:
        raise ValueError("schema_version must not be empty.")
    normalized = version[1:] if version.lower().startswith("v") else version
    if normalized not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"Unsupported schema version: {version!r}.")
    return normalized


SchemaVersion = Annotated[str, BeforeValidator(validate_schema_version)]


def validate_evidence_schema_version(value: object, _info: ValidationInfo) -> str:
    """Normalize and validate the evidence contract schema version.

    Mirrors ``validate_schema_version`` but is scoped to the sole supported
    evidence revision (``1.2``). It tolerates a leading ``v`` prefix that some
    LLM producers emit (e.g. ``"v1.2"``) and returns the canonical ``"1.2"``.
    """
    if not isinstance(value, str):
        raise ValueError("schema_version must be a string.")
    version = value.strip()
    if not version:
        raise ValueError("schema_version must not be empty.")
    normalized = version[1:] if version.lower().startswith("v") else version
    if normalized != EVIDENCE_CONTRACT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported evidence schema version: {version!r}.")
    return normalized


EvidenceSchemaVersion = Annotated[str, BeforeValidator(validate_evidence_schema_version)]
