"""Structured AI output for candidate profile extraction.

Represents the structured data an extractor produces from a candidate resume.
Contact details, links, and education/language/certification lists are optional
because not every resume carries them; the extractor only emits values it can
ground in the resume text (phone numbers, e-mail addresses, and profile URLs are
never invented). When absent the consumer renders a graceful "not found" state
instead of fabricating a value.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.ai.contracts.schema import AI_CONTRACT_SCHEMA_VERSION, SchemaVersion


class CandidateProfileExtractionOutput(BaseModel):
    """A candidate profile extracted from a resume (schema v1.0)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = AI_CONTRACT_SCHEMA_VERSION
    full_name: Annotated[str, Field(min_length=1)]
    summary: str | None = None
    skills: Annotated[list[str], Field(default_factory=list)]
    experience: Annotated[list[str], Field(default_factory=list)]
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    education: Annotated[list[str], Field(default_factory=list)]
    languages: Annotated[list[str], Field(default_factory=list)]
    certifications: Annotated[list[str], Field(default_factory=list)]
