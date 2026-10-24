from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.api.v1.schemas.candidate_pool import JobCandidateSummary
from app.api.v1.schemas.evaluations import CandidateEvaluationResponse
from app.api.v1.schemas.job_applications import JobApplicationResponse
from app.api.v1.schemas.jobs import JobResponse
from app.api.v1.schemas.match_evidence import MatchEvidenceResponse


class ReviewCandidateInfo(BaseModel):
    """Candidate display data used by the review screen.

    Uses ``name`` (instead of the API ``full_name``) to line up with the
    review page's display model.
    """

    id: UUID
    name: str
    email: str | None = None
    phone: str | None = None


class ReviewBundleResponse(BaseModel):
    """Everything the review screen needs for one application.

    Read-only aggregation: application, candidate, job, all evaluation
    versions, the current evaluation, its evidence, and the candidate's pool
    ranking context (group, latest HR decision).
    """

    model_config = ConfigDict(from_attributes=True)

    application: JobApplicationResponse
    candidate: ReviewCandidateInfo
    job: JobResponse
    evaluations: list[CandidateEvaluationResponse]
    evaluation: CandidateEvaluationResponse | None
    evidence: list[MatchEvidenceResponse]
    pool_row: JobCandidateSummary | None
