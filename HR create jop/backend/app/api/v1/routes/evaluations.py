import uuid as _uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.evaluations import CandidateEvaluationResponse
from app.api.v1.schemas.match_evidence import MatchEvidenceResponse
from app.core.database import get_db
from app.models import MatchEvidence
from app.services.evaluation_service import EvaluationService

router = APIRouter()


@router.get(
    "/job-applications/{application_id}/evaluations",
    response_model=list[CandidateEvaluationResponse],
)
def list_evaluations(
    application_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return EvaluationService().list_versions(
        db,
        job_application_id=_uuid.UUID(application_id),
        organization_id=ctx.organization_id,
    )


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=CandidateEvaluationResponse,
)
def get_evaluation(
    evaluation_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return EvaluationService().get_version(
        db,
        evaluation_id=_uuid.UUID(evaluation_id),
        organization_id=ctx.organization_id,
    )


@router.get(
    "/evaluations/{evaluation_id}/evidence",
    response_model=list[MatchEvidenceResponse],
)
def list_evaluation_evidence(
    evaluation_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    EvaluationService().get_version(
        db,
        evaluation_id=_uuid.UUID(evaluation_id),
        organization_id=ctx.organization_id,
    )
    return list(
        db.scalars(
            select(MatchEvidence)
            .where(MatchEvidence.candidate_evaluation_id == _uuid.UUID(evaluation_id))
            .order_by(MatchEvidence.created_at)
        )
    )
