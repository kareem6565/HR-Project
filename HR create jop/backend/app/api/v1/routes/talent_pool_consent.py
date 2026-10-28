from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, require_roles
from app.api.v1.schemas.talent_pool_consent import (
    ConsentLinkDecisionRequest,
    ConsentLinkDecisionResponse,
    ConsentLinkPreviewRequest,
    ConsentLinkPreviewResponse,
    ConsentLinkResponse,
    ConsentWithdrawalRequest,
)
from app.core.database import get_db
from app.services.candidate_service import CandidateService
from app.services.talent_pool_consent_service import TalentPoolConsentService

router = APIRouter()


@router.post(
    "/candidates/{candidate_id}/talent-pool-consent-link",
    response_model=ConsentLinkResponse,
    status_code=201,
)
def create_talent_pool_consent_link(
    candidate_id: str,
    ctx: RequestContext = Depends(require_roles("admin", "recruiter")),
    db: Session = Depends(get_db),
):
    token, expires_at = TalentPoolConsentService().create_link(
        db,
        candidate_id=uuid.UUID(candidate_id),
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
    )
    db.commit()
    return ConsentLinkResponse(token=token, expires_at=expires_at)


@router.post(
    "/candidates/{candidate_id}/talent-pool-consent/withdraw",
    status_code=200,
)
def withdraw_talent_pool_consent(
    candidate_id: str,
    body: ConsentWithdrawalRequest,
    ctx: RequestContext = Depends(require_roles("admin", "recruiter")),
    db: Session = Depends(get_db),
):
    CandidateService().get(
        db, candidate_id=uuid.UUID(candidate_id), organization_id=ctx.organization_id
    )
    withdrawn = TalentPoolConsentService().withdraw(
        db,
        candidate_id=uuid.UUID(candidate_id),
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
    )
    db.commit()
    return {"withdrawn": withdrawn}


@router.post(
    "/candidate-portal/talent-pool-consent/preview",
    response_model=ConsentLinkPreviewResponse,
)
def preview_talent_pool_consent(
    body: ConsentLinkPreviewRequest,
    db: Session = Depends(get_db),
):
    result = TalentPoolConsentService().preview(db, token=body.token)
    return ConsentLinkPreviewResponse(**result)


@router.post(
    "/candidate-portal/talent-pool-consent/respond",
    response_model=ConsentLinkDecisionResponse,
)
def respond_to_talent_pool_consent(
    body: ConsentLinkDecisionRequest,
    db: Session = Depends(get_db),
):
    expires_at = TalentPoolConsentService().respond(
        db, token=body.token, decision=body.decision
    )
    db.commit()
    return ConsentLinkDecisionResponse(
        decision=body.decision, consent_expires_at=expires_at
    )
