from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

FieldOrigin = Literal[
    "hera_suggested",
    "hr_entered_or_edited",
    "hr_edited_after_hera_suggestion",
    "not_provided",
]
JOB_FIELD_ORIGINS = frozenset(
    {
        "title",
        "department",
        "location",
        "type",
        "experience",
        "description",
        "requirementsText",
        "requiredSkillsText",
    }
)


class JobSourceMetadata(BaseModel):
    """User-supplied source details; review identity and time are server-owned."""

    source_name: str = Field(min_length=1, max_length=120)
    source_url: AnyHttpUrl | None = None
    published_at: date | None = None
    application_url: AnyHttpUrl | None = None
    source_import_id: str = Field(min_length=1, max_length=64)
    review_confirmed: bool

    @field_validator("source_name")
    @classmethod
    def normalize_source_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Source name cannot be blank.")
        return normalized

class JobProfileCreate(BaseModel):
    status: str
    source: str
    profile_data: dict[str, Any]
    raw_input_snapshot: dict[str, Any] | None = None
    source_original_listing_text: str | None = Field(default=None, max_length=50_000)
    source_metadata: JobSourceMetadata | None = None
    field_origins: dict[str, FieldOrigin] | None = None

    @field_validator("field_origins")
    @classmethod
    def validate_field_origins(
        cls, value: dict[str, FieldOrigin] | None
    ) -> dict[str, FieldOrigin] | None:
        if value is not None and not set(value).issubset(JOB_FIELD_ORIGINS):
            raise ValueError("Field origins contain an unknown job field.")
        return value


class JobProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    version_number: int
    status: str
    source: str
    profile_data: dict[str, Any]
    raw_input_snapshot: dict[str, Any] | None
    provenance: dict[str, Any] | None
    is_current: bool
    created_at: datetime
    updated_at: datetime
