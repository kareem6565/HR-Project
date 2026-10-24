"""Structured AI output for matching evidence.

Represents a single piece of matching evidence connecting a candidate to a
specific job requirement. Evidence is explicitly non-decisional: this contract
must NOT produce or imply an HR decision, a final score, or any authorization
outcome. Only the evidence fields mirroring the ``MatchEvidence`` model (and
its documented ``evidence_type`` constraint) are included.

Phase 4.2 (schema v1.2) requires each evidence item to identify which job
requirement it concerns via a ``requirement_ref`` carrying a mandatory
``requirement_key``. Callers validate that every supplied ``requirement_key``
exists in the exact key set given to the producer; the contract's regex alone
does not guarantee that.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.contracts.schema import (
    EVIDENCE_CONTRACT_SCHEMA_VERSION,
    EvidenceSchemaVersion,
)


class MatchEvidenceOutput(BaseModel):
    """A single matching evidence item for a candidate evaluation (schema v1.2)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: EvidenceSchemaVersion = EVIDENCE_CONTRACT_SCHEMA_VERSION
    evidence_type: Literal["matched", "missing", "partial"]
    requirement_ref: dict[str, Any] = Field(
        ...,
        description=(
            "Must identify the job requirement this evidence concerns via a "
            "``requirement_key`` value matching ``^req-[0-9a-f]{16}$``."
        ),
    )
    candidate_evidence: dict[str, Any] | None = None
    strength: str | None = None
    provenance: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _require_requirement_key(self) -> "MatchEvidenceOutput":
        key = self.requirement_ref.get("requirement_key")
        if not isinstance(key, str) or not is_requirement_key(key):
            raise ValueError("requirement_ref must contain a valid requirement_key.")
        return self


class MatchEvidenceListOutput(BaseModel):
    """A list of matching evidence items covering the job requirements (schema v1.2)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: EvidenceSchemaVersion = EVIDENCE_CONTRACT_SCHEMA_VERSION
    evidence_items: list[MatchEvidenceOutput]
    provenance: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _reject_duplicate_requirement_keys(self) -> "MatchEvidenceListOutput":
        seen: set[str] = set()
        for item in self.evidence_items:
            key = item.requirement_ref["requirement_key"]
            if key in seen:
                raise ValueError(f"Duplicate evidence requirement_key {key!r}.")
            seen.add(key)
        return self


def is_requirement_key(value: str) -> bool:
    """Return whether a string matches the system-generated requirement key pattern."""
    if not isinstance(value, str):
        return False
    return (
        len(value) == 20
        and value.startswith("req-")
        and all(char in "0123456789abcdef" for char in value[4:])
    )
