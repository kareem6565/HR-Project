"""Structured, reviewable job-description drafts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.contracts.job_profile import JobRequirement
from app.ai.contracts.schema import JOB_PROFILE_EXTRACTION_SCHEMA_VERSION, SchemaVersion


class JobDescriptionDraftOutput(BaseModel):
    """Job details and categorized criteria proposed for HR review."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = JOB_PROFILE_EXTRACTION_SCHEMA_VERSION
    title: Annotated[str, Field(min_length=1, max_length=255)]
    summary: Annotated[str | None, Field(max_length=4000)] = None
    requirements: Annotated[list[JobRequirement], Field(default_factory=list, max_length=80)]
    needs_confirmation: Annotated[list[str], Field(default_factory=list, max_length=30)]

    @field_validator("title", "summary", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return " ".join(value.split()) if isinstance(value, str) else value

    @field_validator("needs_confirmation", mode="before")
    @classmethod
    def normalize_confirmation_items(cls, value):
        if not isinstance(value, list):
            return value
        return [" ".join(item.split()) if isinstance(item, str) else item for item in value]


JobDescriptionOperation = Literal["generate", "parse", "improve"]


def priority_is_explicit(category: str, source_quote: str | None) -> bool:
    """Only treat a source quote as decisive when its priority is stated there."""
    if category == "important":
        return False
    quote = (source_quote or "").casefold()
    terms = (
        ("required", "must have", "essential", "mandatory", "must-have")
        if category == "must_have"
        else ("preferred", "optional", "nice to have", "bonus", "desirable")
    )
    return any(term in quote for term in terms)


def quote_supports_requirement(text: str, source_quote: str | None) -> bool:
    """Require a pasted-source quote to contain the proposed requirement text."""
    requirement = " ".join(text.split()).casefold()
    quote = " ".join((source_quote or "").split()).casefold()
    return bool(requirement and quote and requirement in quote)
