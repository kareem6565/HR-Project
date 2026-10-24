from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AIActivityStepResponse(BaseModel):
    name: str
    status: str
    duration_ms: int | None = None


class AIActivityRunResponse(BaseModel):
    """One workflow execution presented for practitioner observability."""

    id: UUID
    run_id: str
    workflow_type: str
    status: str
    title: str
    candidate_name: str | None = None
    job_title: str | None = None
    provider: str | None = None
    model: str | None = None
    timestamp: datetime | None = None
    total_duration_ms: int | None = None
    steps: list[AIActivityStepResponse] = Field(default_factory=list)
    schema_version: str | None = None
    prompt: str | None = None


class AIActivityStatsResponse(BaseModel):
    total_runs_24h: int
    successful: int
    failed: int
    avg_latency_ms: int | None = None


class AIActivityRetryResponse(BaseModel):
    run_id: UUID
    status: str
