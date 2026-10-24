"""Structured AI output for the job-form auto-fill suggestion (advisory).

Represents the advisory field suggestions HERA proposes from a raw job
description so HR can start from a pre-filled JobForm draft. This contract is
strictly advisory: it never persists anything, never creates a Job or a
JobProfile, never scores, matches, or makes a hiring decision, and carries no
confidence fields. The schema mirrors the fields the ``jobs`` table actually
stores so suggested values map 1:1 onto the JobForm, with the same column
length ceilings applied before anything could later be saved.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.contracts.schema import AI_CONTRACT_SCHEMA_VERSION, SchemaVersion


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def _normalize_list(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        text = _normalize_text(item)
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        normalized.append(text)
    return normalized


class JobDraftSuggestionOutput(BaseModel):
    """Advisory job-form field suggestions extracted from a job description."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = AI_CONTRACT_SCHEMA_VERSION
    title: Annotated[str | None, Field(max_length=255)] = None
    department: Annotated[str | None, Field(max_length=100)] = None
    location: Annotated[str | None, Field(max_length=100)] = None
    job_type: Annotated[str | None, Field(max_length=50)] = None
    experience: Annotated[str | None, Field(max_length=100)] = None
    requirements: Annotated[list[str], Field(default_factory=list, max_length=50)]
    required_skills: Annotated[list[str], Field(default_factory=list, max_length=50)]

    @field_validator("title", "department", "location", "job_type", "experience", mode="before")
    @classmethod
    def _clean_optional_text(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        cleaned = _normalize_text(value)
        return cleaned or None

    @field_validator("requirements", "required_skills", mode="before")
    @classmethod
    def _clean_list(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        return _normalize_list(value)
