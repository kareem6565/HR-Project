import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.interview_question_sets import (
    InterviewQuestionSetCreate,
    InterviewQuestionSetListResponse,
    InterviewQuestionSetResponse,
    InterviewQuestionSetUpdate,
)
from app.core.database import get_db
from app.services.errors import NotFoundError, ValidationError
from app.services.interview_question_service import InterviewQuestionService

router = APIRouter()


@router.post(
    "/job-applications/{application_id}/question-sets/generate",
    response_model=InterviewQuestionSetResponse,
    status_code=201,
)
def generate_interview_question_set(
    application_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Generate an AI interview question set for an application (HR may then edit/approve)."""
    from app.ai.providers import get_provider
    from app.ai.providers.errors import ProviderError
    from app.ai.providers.factory import resolve_ai_config
    from app.ai.workflows import InterviewQuestionGenerationWorkflow
    from app.core.config import settings
    from app.models import JobApplication

    application_uuid = uuid.UUID(application_id)
    application = db.get(JobApplication, application_uuid)
    if application is None or application.organization_id != ctx.organization_id:
        raise NotFoundError("JobApplication was not found.")

    payload = _derive_question_payload(
        db,
        application=application,
        organization_id=ctx.organization_id,
    )
    if not resolve_ai_config(settings)["is_fake"]:
        provider = get_provider(settings)
    else:
        provider = get_provider(
            settings,
            provider="fake",
            model="fake-interview-question-model",
            structured_payload=payload,
        )
    workflow = InterviewQuestionGenerationWorkflow(provider=provider)
    try:
        result = workflow.run(
            db,
            job_application_id=application_uuid,
            organization_id=ctx.organization_id,
        )
    except ProviderError:
        db.rollback()
        raise
    db.commit()
    question_set = InterviewQuestionService().get(
        db,
        question_set_id=result.question_set_id,
        organization_id=ctx.organization_id,
    )
    return _to_response(question_set)


@router.get(
    "/job-applications/{application_id}/question-sets",
    response_model=InterviewQuestionSetListResponse,
)
def list_interview_question_sets(
    application_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """List all question-set versions for an application (HR history)."""
    versions = InterviewQuestionService().list_for_application(
        db,
        job_application_id=uuid.UUID(application_id),
        organization_id=ctx.organization_id,
    )
    current_id = None
    for version in versions:
        if version.is_current:
            current_id = version.id
    return InterviewQuestionSetListResponse(
        question_sets=[_to_response(version) for version in reversed(versions)],
        current_id=_current_question_set_id(db, application_id, ctx.organization_id) or current_id,
        total=len(versions),
    )


@router.post(
    "/job-applications/{application_id}/question-sets",
    response_model=InterviewQuestionSetResponse,
    status_code=201,
)
def create_interview_question_set(
    application_id: str,
    body: InterviewQuestionSetCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Create an HR-curated draft question set for an application.

    HR selects/edits questions from the prep workspace and saves them as a
    new ``generated`` draft (``generated_by="hr"``, ``provenance`` marks the
    interview-prep path). The draft is never auto-approved; an HR-approval
    in the Question Set Builder turns it into the current set. Approved sets
    are never modified — Saves after an approval always create a fresh draft.
    """
    question_set = InterviewQuestionService().create_version(
        db,
        job_application_id=uuid.UUID(application_id),
        status="generated",
        questions=[question.model_dump() for question in body.questions],
        generated_by="hr",
        provenance={"source": "interview_prep"},
        organization_id=ctx.organization_id,
    )
    db.commit()
    return _to_response(question_set)


@router.get(
    "/interview-question-sets/{question_set_id}",
    response_model=InterviewQuestionSetResponse,
)
def get_interview_question_set(
    question_set_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    question_set = InterviewQuestionService().get(
        db,
        question_set_id=uuid.UUID(question_set_id),
        organization_id=ctx.organization_id,
    )
    return _to_response(question_set)


@router.put(
    "/interview-question-sets/{question_set_id}",
    response_model=InterviewQuestionSetResponse,
)
def update_interview_question_set(
    question_set_id: str,
    body: InterviewQuestionSetUpdate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Select / edit / reorder / add / remove questions on a non-approved set."""
    question_set = InterviewQuestionService().update_questions(
        db,
        question_set_id=uuid.UUID(question_set_id),
        questions=[question.model_dump() for question in body.questions],
        organization_id=ctx.organization_id,
    )
    db.commit()
    return _to_response(question_set)


@router.post(
    "/interview-question-sets/{question_set_id}/approve",
    response_model=InterviewQuestionSetResponse,
)
def approve_interview_question_set(
    question_set_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Approve a question set; it becomes the current approved set for the application."""
    question_set = InterviewQuestionService().approve(
        db,
        question_set_id=uuid.UUID(question_set_id),
        approved_by_user_id=ctx.user_id,
        organization_id=ctx.organization_id,
    )
    db.commit()
    return _to_response(question_set)


def _to_response(question_set) -> InterviewQuestionSetResponse:
    payload = InterviewQuestionService.to_response(question_set)
    return InterviewQuestionSetResponse(**payload)


def _current_question_set_id(
    db: Session, application_id: str, organization_id: uuid.UUID
) -> uuid.UUID | None:
    current = InterviewQuestionService().get_current_or_latest(
        db,
        job_application_id=uuid.UUID(application_id),
        organization_id=organization_id,
    )
    return current.id if current is not None else None


def _derive_question_payload(db: Session, *, application, organization_id: uuid.UUID) -> dict:
    """Construct a deterministic, valid question-set payload in fake-provider mode.

    Grounds questions in the approved JobProfile's readable requirement topics,
    the candidate's current skills, and evidence gaps — so the fallback set is
    always real-data-rooted and passes contract validation.
    """
    from app.ai.contracts import normalize_job_profile_requirements
    from app.services.job_profile_service import JobProfileService

    service = InterviewQuestionService()
    requirements: list[dict] = []
    approved_profile = None
    for version in JobProfileService().list_versions(
        db, job_id=application.job_id, organization_id=organization_id
    ):
        if version.status == "approved":
            approved_profile = version
            break
    if approved_profile is not None:
        requirements = [
            {"key": requirement.key, "text": requirement.text}
            for requirement in normalize_job_profile_requirements(
                approved_profile.profile_data.get("requirements")
            )
        ]
    skills = service.collect_candidate_skills(
        db,
        candidate=application.candidate,
        organization_id=organization_id,
    )
    gaps = service.collect_candidate_gaps(db, application=application)

    def guide(purpose: str, basis: str, looks_for: str) -> dict:
        return {
            "purpose": purpose,
            "evidence_basis": basis,
            "source_quote": None,
            "interviewer_looks_for": looks_for,
            "evaluation_rubric": [
                "Explains the approach with a clear sequence.",
                "Uses a concrete example or relevant trade-offs.",
                "Identifies how success or correctness would be checked.",
            ],
        }

    questions: list[dict] = []
    for requirement in requirements[:3]:
        questions.append(
            {
                "category": "technical",
                "text": (
                    f"Walk me through your hands-on experience with "
                    f"{requirement['text']} in a real project."
                ),
                "topic": requirement["text"],
                "requirement_key": requirement["key"],
                "review_guide": guide(
                    f"Explore practical experience with {requirement['text']}.",
                    "job_requirement",
                    "A relevant method, example, and trade-offs.",
                ),
            }
        )
    for skill in skills[:2]:
        questions.append(
            {
                "category": "candidate_specific",
                "text": (
                    f"What is your experience with {skill}, and how have you applied it in a project?"
                ),
                "topic": skill,
                "requirement_key": None,
                "review_guide": guide(
                    f"Verify the candidate's experience with {skill}.",
                    "verification_question",
                    "A specific, technically coherent example from the candidate.",
                ),
            }
        )
    for gap in gaps[:1]:
        questions.append(
            {
                "category": "candidate_specific",
                "text": (
                    f"How would you approach a task that requires {gap}?"
                ),
                "topic": gap,
                "requirement_key": None,
                "review_guide": guide(
                    f"Verify the candidate's approach to {gap}.",
                    "verification_question",
                    "A practical learning or problem-solving plan, including risks.",
                ),
            }
        )
    questions.append(
        {
            "category": "behavioral",
            "text": (
                "Describe a time you disagreed with a technical decision during a "
                "project. How did you resolve it?"
            ),
            "topic": None,
            "requirement_key": None,
            "review_guide": guide(
                "Understand how the candidate handles technical disagreement.",
                "job_requirement",
                "Listening, evidence-based reasoning, and a constructive outcome.",
            ),
        }
    )
    return {"schema_version": "1.2", "questions": questions}
