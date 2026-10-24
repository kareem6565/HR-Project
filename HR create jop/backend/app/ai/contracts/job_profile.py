"""Structured AI output for job profile extraction.

Represents the structured data an extractor produces from a raw job
description. The schema is intentionally minimal: it captures only fields
already justified by the repository so far, and stores richer detail under
explicitly typed fields rather than a speculative nested structure.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai.contracts.schema import JOB_PROFILE_EXTRACTION_SCHEMA_VERSION, SchemaVersion

RequirementCategory = Literal["must_have", "important", "nice_to_have"]
RequirementDimension = Literal["skill", "experience", "education", "responsibility"]
JobQualityFindingType = Literal[
    "unclear_requirement",
    "potential_conflict",
    "priority_unclear",
    "not_measurable",
]

REQUIREMENT_CATEGORIES: tuple[RequirementCategory, ...] = (
    "must_have",
    "important",
    "nice_to_have",
)

REQUIREMENT_DIMENSIONS: tuple[RequirementDimension, ...] = (
    "skill",
    "experience",
    "education",
    "responsibility",
)


def _normalize_text(value: str) -> str:
    """Normalize requirement text for keying: strip and collapse whitespace."""
    return " ".join(value.strip().split())


def requirement_key(text: str, category: str) -> str:
    """Deterministically derive the system-owned key for a requirement.

    The key is always system-generated from the normalized text plus the
    category; the LLM never supplies it. Requirements sharing a normalized
    text and category always produce the same key, so duplicate keys are
    rejected at persistence boundaries and reads stay stable across versions.
    """
    digest = hashlib.sha256(f"{category}\x00{_normalize_text(text)}".encode()).hexdigest()
    return f"req-{digest[:16]}"


class JobRequirement(BaseModel):
    """A single structured job requirement (contract schema v1.1).

    The LLM proposes only ``text``, ``category``, and ``dimension``. The
    ``key`` is always recomputed by ``requirement_key()``; any key present in
    the input is stripped and never trusted or persisted as supplied.
    """

    model_config = ConfigDict(extra="forbid")

    key: str = ""
    text: Annotated[str, Field(min_length=1)]
    category: RequirementCategory
    dimension: RequirementDimension

    @model_validator(mode="before")
    @classmethod
    def _normalize_input(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = {name: item for name, item in value.items() if name != "key"}
        if isinstance(payload.get("text"), str):
            payload["text"] = _normalize_text(payload["text"])
        return payload

    @model_validator(mode="after")
    def _assign_system_key(self) -> JobRequirement:
        self.key = requirement_key(self.text, self.category)
        return self


class JobDescriptionQualityFinding(BaseModel):
    """A source-grounded issue for HR to review; never a replacement requirement."""

    model_config = ConfigDict(extra="forbid")

    finding_type: JobQualityFindingType
    source_quote: Annotated[str, Field(min_length=1)]
    concern: Annotated[str, Field(min_length=1)]
    question_for_hr: Annotated[str, Field(min_length=1)]


class JobDescriptionQualityReview(BaseModel):
    """Optional advisory findings extracted from a job description."""

    model_config = ConfigDict(extra="forbid")

    findings: Annotated[list[JobDescriptionQualityFinding], Field(default_factory=list)]


class JobProfileExtractionOutput(BaseModel):
    """A job profile extracted from a raw job description (schema v1.2).

    ``requirements`` accepts the v1.0 flat ``list[str]`` shape and v1.1
    structured requirements for read compatibility. The optional v1.2 quality
    review is advisory and quote-verified before persistence.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = JOB_PROFILE_EXTRACTION_SCHEMA_VERSION
    title: Annotated[str, Field(min_length=1)]
    summary: str | None = None
    requirements: Annotated[list[JobRequirement], Field(default_factory=list)]
    quality_review: JobDescriptionQualityReview | None = None

    @field_validator("requirements", mode="before")
    @classmethod
    def _coerce_requirements(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        if any(isinstance(item, str) for item in value):
            if any(isinstance(item, dict) for item in value):
                raise ValueError(
                    "Job profile requirements must not mix v1.0 strings and v1.1 structures."
                )
            return [{"text": item, "category": "important", "dimension": "skill"} for item in value]
        return value

    @model_validator(mode="after")
    def _reject_duplicate_requirement_keys(self) -> JobProfileExtractionOutput:
        seen: dict[str, str] = {}
        for requirement in self.requirements:
            if requirement.key in seen:
                raise ValueError(
                    f"Duplicate requirement key {requirement.key!r} for texts "
                    f"{seen[requirement.key]!r} and {requirement.text!r}."
                )
            seen[requirement.key] = requirement.text
        return self
