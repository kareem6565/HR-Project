from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.github_evidence import (
    GitHubEvidenceAnalysisResponse,
    GitHubEvidenceDecisionRequest,
    GitHubEvidencePreviewRequest,
    GitHubEvidencePreviewResponse,
    GitHubEvidenceRequest,
    GitHubEvidenceStartResponse,
)
from app.core.database import get_db
from app.services.github_evidence_service import GitHubEvidenceService

router = APIRouter()
public_router = APIRouter()


def _response(row):
    if row is None:
        return None
    return GitHubEvidenceAnalysisResponse(
        id=row.id,
        status=row.status,
        repository_urls=row.repository_urls,
        evidence=row.evidence or [],
        assessments=row.assessments or [],
        error_code=row.error_code,
        attempts=row.attempts,
        consent_responded_at=row.consent_responded_at,
        consent_link_expires_at=row.consent_link_expires_at,
        retry_after_at=row.retry_after_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post(
    "/applications/{application_id}/github-evidence/consent-link",
    response_model=GitHubEvidenceStartResponse,
    status_code=201,
)
def create_github_evidence_consent_link(
    application_id: str,
    body: GitHubEvidenceRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    row, token = GitHubEvidenceService().create_consent_link(
        db,
        application_id=uuid.UUID(application_id),
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        repository_urls=body.repository_urls,
    )
    db.commit()
    return GitHubEvidenceStartResponse(
        analysis_id=row.id,
        status=row.status,
        consent_url=f"/github-evidence/consent#{token}",
        consent_link_expires_at=row.consent_link_expires_at,
    )


@router.get(
    "/applications/{application_id}/github-evidence/latest",
    response_model=GitHubEvidenceAnalysisResponse | None,
)
def get_latest_github_evidence(
    application_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    row = GitHubEvidenceService().get_latest(
        db, application_id=uuid.UUID(application_id), organization_id=ctx.organization_id
    )
    return _response(row)


@router.post(
    "/applications/{application_id}/github-evidence/{analysis_id}/retry",
    response_model=GitHubEvidenceAnalysisResponse,
)
def retry_github_evidence(
    application_id: str,
    analysis_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    row = GitHubEvidenceService().get_latest(
        db, application_id=uuid.UUID(application_id), organization_id=ctx.organization_id
    )
    if row is None or row.id != uuid.UUID(analysis_id):
        from app.services.errors import NotFoundError

        raise NotFoundError("GitHub evidence analysis was not found.")
    row = GitHubEvidenceService().retry(db, analysis_id=row.id, organization_id=ctx.organization_id)
    db.commit()
    return _response(row)


@public_router.post(
    "/candidate-portal/github-evidence-consent/preview",
    response_model=GitHubEvidencePreviewResponse,
)
def preview_github_evidence_consent(
    body: GitHubEvidencePreviewRequest,
    db: Session = Depends(get_db),
):
    return GitHubEvidenceService().preview(db, token=body.token)


@public_router.post(
    "/candidate-portal/github-evidence-consent/respond",
    response_model=GitHubEvidenceAnalysisResponse,
)
def respond_to_github_evidence_consent(
    body: GitHubEvidenceDecisionRequest,
    db: Session = Depends(get_db),
):
    row = GitHubEvidenceService().respond(db, token=body.token, decision=body.decision)
    db.commit()
    return _response(row)
