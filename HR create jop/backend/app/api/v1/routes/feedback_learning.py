from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.feedback_learning import (
    BenchmarkRequest,
    BenchmarkResponse,
    CorrectionCreateRequest,
    CorrectionResponse,
    FeedbackAnalyticsResponse,
    ProposeSkillAliasRequest,
    ProposeSkillAliasResponse,
)
from app.core.database import get_db
from app.services.feedback_learning_service import FeedbackLearningService

router = APIRouter()


@router.post(
    "/feedback/corrections",
    response_model=CorrectionResponse,
    status_code=201,
)
def record_hr_correction(
    body: CorrectionCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Record structured HR correction on AI output (Stage K learning loop)."""
    correction = FeedbackLearningService().record_correction(
        db,
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        correction_type=body.correction_type,
        job_id=body.job_id,
        job_profile_id=body.job_profile_id,
        candidate_profile_id=body.candidate_profile_id,
        candidate_evaluation_id=body.candidate_evaluation_id,
        job_application_id=body.job_application_id,
        original_ai_output=body.original_ai_output,
        hr_corrected_result=body.hr_corrected_result,
        reason=body.reason,
        evidence_reference=body.evidence_reference,
        provider_info=body.provider_info,
    )
    db.commit()
    return correction


@router.get(
    "/feedback/corrections",
    response_model=list[CorrectionResponse],
)
def list_hr_corrections(
    correction_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """List recorded HR corrections."""
    return FeedbackLearningService().list_corrections(
        db,
        organization_id=ctx.organization_id,
        correction_type=correction_type,
        limit=limit,
    )


@router.get(
    "/feedback/analytics",
    response_model=FeedbackAnalyticsResponse,
)
def get_feedback_analytics(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Return analytics on AI error frequency, override rates, and correction types."""
    analytics = FeedbackLearningService().get_analytics(
        db,
        organization_id=ctx.organization_id,
    )
    return FeedbackAnalyticsResponse(**analytics)


@router.post(
    "/feedback/aliases/propose",
    response_model=ProposeSkillAliasResponse,
)
def propose_skill_alias(
    body: ProposeSkillAliasRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Propose and activate a new skill alias derived from approved HR corrections."""
    res = FeedbackLearningService().propose_skill_alias(
        db,
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        alias=body.alias,
        canonical_skill=body.canonical_skill,
        reason=body.reason,
    )
    db.commit()
    return ProposeSkillAliasResponse(**res)


@router.post(
    "/feedback/evaluation-run",
    response_model=BenchmarkResponse,
)
def run_benchmark_evaluation(
    body: BenchmarkRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Evaluate matching rule improvements against a controlled benchmark dataset."""
    cases = [case.model_dump() for case in body.test_cases]
    res = FeedbackLearningService().evaluate_rules_on_dataset(
        db,
        organization_id=ctx.organization_id,
        test_cases=cases,
    )
    return BenchmarkResponse(**res)
