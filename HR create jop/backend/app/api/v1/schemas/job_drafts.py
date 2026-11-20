"""Request/response schemas for the advisory job-form auto-fill endpoint."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.ai.contracts.job_description import JobDescriptionDraftOutput


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


class JobDescriptionBuilderRequest(BaseModel):
    """Bounded inputs for generating, parsing, or improving a draft."""

    operation: Literal["generate", "parse", "improve"]
    title: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=100)
    seniority: str | None = Field(default=None, max_length=100)
    employment_type: str | None = Field(default=None, max_length=50)
    work_mode: str | None = Field(default=None, max_length=30)
    location: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=100)
    role_context: str | None = Field(default=None, max_length=4000)
    additional_requirements: str | None = Field(default=None, max_length=4000)
    experience_expectations: str | None = Field(default=None, max_length=500)
    source_text: str | None = Field(default=None, max_length=50_000)
    selected_section: str | None = Field(default=None, max_length=4000)
    section_name: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_operation_inputs(self):
        if self.operation == "generate" and not (self.title and self.department):
            raise ValueError("Job title and department are required to generate a description.")
        if self.operation == "parse" and not (self.source_text and self.source_text.strip()):
            raise ValueError("Paste a job description to analyze it.")
        if self.operation == "improve" and not (self.selected_section and self.section_name):
            raise ValueError("Choose a section and provide its current text for AI assistance.")
        return self


class JobDescriptionBuilderResponse(JobDescriptionDraftOutput):
    """A structured suggestion returned for HR review; never auto-approved."""

    creation_method: Literal["ai_generated", "pasted_external", "manual"]
