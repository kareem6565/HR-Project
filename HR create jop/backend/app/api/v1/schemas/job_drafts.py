"""Request/response schemas for the advisory job-form auto-fill endpoint."""

from pydantic import BaseModel, Field


class JobDraftSuggestionRequest(BaseModel):
    """A raw job description to base advisory form suggestions on."""

    raw_description: str = Field(min_length=1, max_length=50_000)


class JobDraftSuggestionResponse(BaseModel):
    """Advisory field suggestions mapped to the JobForm (never persisted).

    All fields are optional because the producer may only be able to suggest
    a subset. Every value still mirrors a persistable ``jobs`` column so the
    frontend can place it directly into the matching form field.
    """

    schema_version: str = "1.1"
    title: str | None = None
    department: str | None = None
    location: str | None = None
    job_type: str | None = None
    experience: str | None = None
    requirements: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
