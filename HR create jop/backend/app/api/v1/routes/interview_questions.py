import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.interview_questions import (
    InterviewQuestion,
    InterviewQuestionsResponse,
)
from app.core.database import get_db
from app.services.interview_question_service import InterviewQuestionService

router = APIRouter()


@router.get(
    "/interview-questions",
    response_model=InterviewQuestionsResponse,
)
def get_interview_questions(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    candidate_id: str | None = Query(default=None),
):
    """Return curated question banks, plus candidate-specific questions when a
    candidate is supplied (built from their real profile skills and gaps)."""
    payload = InterviewQuestionService().get_questions(
        db,
        organization_id=ctx.organization_id,
        candidate_id=uuid.UUID(candidate_id) if candidate_id else None,
    )
    return InterviewQuestionsResponse(
        categories=payload["categories"],
        questions={
            category: [InterviewQuestion(**item) for item in items]
            for category, items in payload["questions"].items()
        },
        candidate_id=payload["candidate_id"],
    )
