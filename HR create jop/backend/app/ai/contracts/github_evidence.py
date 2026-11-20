from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class GitHubRequirementAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_key: Annotated[str, Field(min_length=1, max_length=64)]
    classification: Literal["direct", "indirect", "insufficient"]
    evidence_ids: Annotated[list[str], Field(max_length=20)] = Field(default_factory=list)
    explanation: Annotated[str, Field(min_length=1, max_length=800)]
    limitations: Annotated[list[str], Field(max_length=8)] = Field(default_factory=list)


class GitHubEvidenceAssessmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessments: Annotated[list[GitHubRequirementAssessment], Field(max_length=100)]
