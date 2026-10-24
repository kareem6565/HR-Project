"""Structured AI output for evaluation explanation.

Contains explanatory text for a candidate evaluation only. It does not include
a recommendation, score, or any decision field: an AI explanation must never
create or imply an HR decision (the HR professional remains the final decision
maker).
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.ai.contracts.schema import AI_CONTRACT_SCHEMA_VERSION, SchemaVersion


class EvaluationExplanationOutput(BaseModel):
    """An AI-generated explanation for a candidate evaluation (schema v1.0)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = AI_CONTRACT_SCHEMA_VERSION
    summary: Annotated[str, Field(min_length=1)]
    points: Annotated[list[str], Field(default_factory=list)]
