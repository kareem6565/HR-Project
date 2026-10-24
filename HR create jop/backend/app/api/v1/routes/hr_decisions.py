import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.hr_decisions import HRDecisionCreate, HRDecisionResponse
from app.core.database import get_db
from app.services.decision_service import DecisionService

router = APIRouter()


@router.post(
    "/job-applications/{application_id}/decisions",
    response_model=HRDecisionResponse,
    status_code=201,
)
def create_hr_decision(
    application_id: str,
    body: HRDecisionCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return DecisionService().create(
        db,
        job_application_id=uuid.UUID(application_id),
        user_id=ctx.user_id,
        decision=body.decision,
        reason=body.reason,
        candidate_evaluation_id=body.candidate_evaluation_id,
        expected_evaluation_id=body.expected_evaluation_id,
        organization_id=ctx.organization_id,
    )
