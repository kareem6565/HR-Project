import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.workflows import (
    CandidateEvaluationRunResponse,
    CandidateProfileExtractionRequest,
    CandidateProfileExtractionResponse,
    JobProfileExtractionResponse,
    JobScreeningResponse,
    ScreenedCandidateResponse,
)
from app.core.database import get_db

router = APIRouter()


@router.post(
    "/jobs/{job_id}/extract-profile",
    response_model=JobProfileExtractionResponse,
    status_code=201,
)
def extract_job_profile(
    job_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Extract a versioned JobProfile draft from a job's raw description.

    Runs the JobProfileExtractionWorkflow through the provider abstraction
    (real Soal provider when configured, deterministic fake payload otherwise) and
    records the AI run in the workflow traces. After a successful extraction
    the job lifecycle moves from ``draft`` to ``awaiting_profile_review``; the
    transition only fires when the job is still a draft.
    """
    from app.ai.providers import get_provider
    from app.ai.providers.factory import resolve_ai_config
    from app.ai.workflows import JobProfileExtractionWorkflow
    from app.core.config import settings
    from app.services.job_service import JobService

    job_uuid = uuid.UUID(job_id)
    job = JobService().get(db, job_id=job_uuid, organization_id=ctx.organization_id)

    if not resolve_ai_config(settings)["is_fake"]:
        provider = get_provider(settings)
    else:
        provider = get_provider(
            settings,
            provider="fake",
            model="fake-model",
            structured_payload=_derive_extraction_payload(job),
        )
    result = JobProfileExtractionWorkflow(provider).run(
        db, job_id=job_uuid, organization_id=ctx.organization_id
    )
    if job.status == "draft":
        job.status = "awaiting_profile_review"
    db.commit()
    return result


@router.post(
    "/jobs/{job_id}/screen",
    response_model=JobScreeningResponse,
    status_code=201,
)
def screen_candidates(
    job_id: str,
    files: list[UploadFile] = File(...),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Screen a batch of uploaded CVs against a job.

    Requires an HR-approved JobProfile for the job. When no approved profile
    exists, screening is rejected and the caller is told to extract a profile
    and approve it in HR review first; screening never auto-appoves a profile.
    For each uploaded file this creates a candidate, stores and parses the
    resume, extracts a candidate profile, attaches the candidate to the job as
    an application, and runs the candidate evaluation workflow.
    """
    from app.ai.providers import get_provider
    from app.ai.workflows import (
        CandidateEvaluationWorkflow,
        CandidateProfileExtractionWorkflow,
    )
    from app.core.config import settings
    from app.models import CandidateEvaluation
    from app.services.candidate_service import CandidateService
    from app.services.errors import ValidationError
    from app.services.job_application_service import JobApplicationService
    from app.services.job_profile_service import JobProfileService
    from app.services.job_service import JobService
    from app.services.resume_details_service import derive_screening_payloads
    from app.services.resume_service import ResumeService
    from app.services.storage_service import LocalFileSystemStorage

    job_uuid = uuid.UUID(job_id)
    job = JobService().get(db, job_id=job_uuid, organization_id=ctx.organization_id)

    job_profile_service = JobProfileService()
    approved_profile = None
    for profile in job_profile_service.list_versions(
        db, job_id=job_uuid, organization_id=ctx.organization_id
    ):
        if profile.status == "approved":
            approved_profile = profile

    if approved_profile is None:
        raise ValidationError(
            "Screening requires an approved JobProfile. "
            "Extract a profile and approve it in HR review before screening candidates."
        )

    from app.services.upload_stream_service import read_batch_bounded

    # Bounded batch reading enforcing max file count, per-file limits, and total batch size
    batch_payloads = read_batch_bounded(
        files,
        max_files=settings.max_batch_files,
        max_file_bytes=settings.max_upload_bytes,
        max_batch_bytes=settings.max_batch_bytes,
    )

    candidate_service = CandidateService()
    resume_service = ResumeService()
    application_service = JobApplicationService()
    storage = LocalFileSystemStorage(settings.storage_root_dir)
    screened: list[ScreenedCandidateResponse] = []
    created_file_uris: list[str] = []

    try:
        with db.begin_nested():
            for payload in batch_payloads:
                candidate = candidate_service.create(
                    db,
                    organization_id=ctx.organization_id,
                    full_name=_candidate_name_from_filename(payload.filename),
                )
                resume = resume_service.create_from_upload(
                    db,
                    candidate_id=candidate.id,
                    organization_id=ctx.organization_id,
                    filename=payload.filename,
                    content_type=payload.content_type,
                    file_bytes=payload.data,
                    max_upload_bytes=settings.max_upload_bytes,
                    storage=storage,
                    checksum=payload.checksum,
                )
                created_file_uris.append(resume.file_uri)

                profile_payload, evidence_payload, explanation_payload = derive_screening_payloads(
                    full_name=candidate.full_name,
                    job_title=job.title,
                    resume_text=resume.extracted_text,
                    requirements=(
                        approved_profile.profile_data.get("requirements")
                        if approved_profile is not None
                        else []
                    ),
                )
                profile_extractor = get_provider(
                    settings,
                    provider="fake",
                    model="fake-model",
                    structured_payload=profile_payload,
                )
                CandidateProfileExtractionWorkflow(profile_extractor).run(
                    db,
                    resume_id=resume.id,
                    organization_id=ctx.organization_id,
                    resume_text=resume.extracted_text,
                )
                application = application_service.create(
                    db,
                    organization_id=ctx.organization_id,
                    job_id=job_uuid,
                    candidate_id=candidate.id,
                    resume_id=resume.id,
                )
                result = CandidateEvaluationWorkflow(
                    evidence_provider=get_provider(
                        settings,
                        provider="fake",
                        model="fake-evidence-model",
                        structured_payload=evidence_payload,
                    ),
                    explanation_provider=get_provider(
                        settings,
                        provider="fake",
                        model="fake-explanation-model",
                        structured_payload=explanation_payload,
                    ),
                ).run(
                    db,
                    job_application_id=application.id,
                    organization_id=ctx.organization_id,
                )
                evaluation = db.get(CandidateEvaluation, result.evaluation_id)
                screened.append(
                    ScreenedCandidateResponse(
                        candidate_id=candidate.id,
                        resume_id=resume.id,
                        application_id=application.id,
                        evaluation_id=result.evaluation_id,
                        score=str(evaluation.score) if evaluation is not None else None,
                    )
                )

        db.commit()
    except Exception:
        for uri in created_file_uris:
            try:
                storage.delete(file_uri=uri)
            except Exception:
                pass
        raise

    return {
        "job_id": job_uuid,
        "job_title": job.title,
        "screened": screened,
    }


def _derive_extraction_payload(job) -> dict:
    """Build a deterministic JobProfileExtractionOutput payload from a job.

    Fake-provider stand-in for the extract step: the suggested profile mirrors
    the job's own title and the same requirement vocabulary the job declares
    (required skills/requirement notes plus professional-experience baseline),
    so the deterministic path stays grounded in real job data.
    """
    return {
        "title": job.title,
        "summary": "Job profile derived from the job's own data.",
        "requirements": _default_job_requirements(job),
    }


def _default_job_requirements(job) -> list[dict[str, str]]:
    """Build default requirements grounded in the job's own data.

    The requirements come from the job's required skills, requirement notes,
    and professional-experience baseline so the deterministic evidence matcher
    grades against the same vocabulary the job actually declares.
    """
    requirements: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in [*(job.required_skills or []), *(job.requirements or [])]:
        text = (value or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        requirements.append({"text": text, "category": "must_have", "dimension": "skill"})
    requirements.append(
        {
            "text": "Relevant professional experience",
            "category": "must_have",
            "dimension": "experience",
        }
    )
    return requirements


def _candidate_name_from_filename(filename: str) -> str:
    """Derive a display name from a CV filename like ``ada-lovelace-cv.pdf``."""
    stem = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
    words = [word for word in stem.split() if word]
    if not words:
        return "Screened Candidate"
    cleaned = [
        word[:1].upper() + word[1:] if word else word
        for word in words
        if any(char.isalnum() for char in word)
    ]
    if not cleaned:
        return "Screened Candidate"
    return " ".join(cleaned)


def _candidate_name_for_resume(
    db: Session,
    *,
    resume_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> str:
    """Resolve the owning candidate's name for a resume, falling back safely."""
    from app.models import Candidate
    from app.services.errors import NotFoundError
    from app.services.resume_service import ResumeService

    resume = ResumeService().get(db, resume_id=resume_id, organization_id=organization_id)
    if resume is None:
        raise NotFoundError("Resume was not found.")
    candidate = db.get(Candidate, resume.candidate_id)
    if candidate is not None and candidate.full_name:
        return candidate.full_name
    return "Extracted Candidate"


@router.post(
    "/resumes/{resume_id}/extract-profile",
    response_model=CandidateProfileExtractionResponse,
    status_code=201,
)
def extract_candidate_profile(
    resume_id: str,
    body: CandidateProfileExtractionRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):

    from app.ai.providers import get_provider
    from app.ai.workflows import CandidateProfileExtractionWorkflow
    from app.core.config import settings
    from app.services.resume_details_service import derive_profile_payload
    from app.services.resume_service import ResumeService

    resume_uuid = uuid.UUID(resume_id)
    if body.resume_text is None:
        resume_text = ResumeService().get_extracted_text(
            db,
            resume_id=resume_uuid,
            organization_id=ctx.organization_id,
        )
    else:
        resume_text = body.resume_text

    provider = get_provider(
        settings,
        provider="fake",
        model="fake-model",
        structured_payload=derive_profile_payload(
            full_name=_candidate_name_for_resume(
                db,
                resume_id=resume_uuid,
                organization_id=ctx.organization_id,
            ),
            resume_text=resume_text,
        ),
    )
    workflow = CandidateProfileExtractionWorkflow(provider)
    result = workflow.run(
        db,
        resume_id=resume_uuid,
        organization_id=ctx.organization_id,
        resume_text=resume_text,
    )
    db.commit()
    return result


@router.post(
    "/job-applications/{application_id}/evaluate",
    response_model=CandidateEvaluationRunResponse,
    status_code=201,
)
def evaluate_candidate(
    application_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    result = _run_candidate_evaluation(
        db,
        application_id=uuid.UUID(application_id),
        organization_id=ctx.organization_id,
    )
    db.commit()
    return result


@router.post(
    "/job-applications/{application_id}/evaluations",
    response_model=CandidateEvaluationRunResponse,
    status_code=201,
)
def evaluate_candidate_alias(
    application_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Trigger the CandidateEvaluation workflow for an application.

    Thin alias of ``POST /job-applications/{application_id}/evaluate`` provided
    as the explicit spec route. Runs the same FakeAIProvider-backed workflow and
    returns the created evaluation identity.
    """
    result = _run_candidate_evaluation(
        db,
        application_id=uuid.UUID(application_id),
        organization_id=ctx.organization_id,
    )
    db.commit()
    return result


def _run_candidate_evaluation(
    db: Session,
    *,
    application_id: uuid.UUID,
    organization_id: uuid.UUID,
):
    from app.ai.providers import get_provider
    from app.ai.workflows import CandidateEvaluationWorkflow
    from app.core.config import settings
    from app.models import JobApplication
    from app.services.errors import NotFoundError, ValidationError
    from app.services.job_profile_service import JobProfileService
    from app.services.job_service import JobService
    from app.services.resume_details_service import (
        derive_evidence_payload,
        derive_explanation_payload,
    )
    from app.services.resume_service import ResumeService

    application = db.get(JobApplication, application_id)
    if application is None or application.organization_id != organization_id:
        raise NotFoundError("JobApplication was not found.")
    job = JobService().get(db, job_id=application.job_id, organization_id=organization_id)
    approved_profile = None
    for profile in JobProfileService().list_versions(
        db, job_id=application.job_id, organization_id=organization_id
    ):
        if profile.status == "approved":
            approved_profile = profile
    requirements = (
        approved_profile.profile_data.get("requirements") if approved_profile is not None else []
    )
    resume = ResumeService().get(
        db,
        resume_id=application.resume_id,
        organization_id=organization_id,
    )
    resume_text = (resume.extracted_text or None) if resume is not None else None

    evidence_payload = derive_evidence_payload(
        resume_text=resume_text,
        requirements=requirements,
    )
    explanation_payload = derive_explanation_payload(
        job_title=job.title,
        requirements=requirements,
        evidence_payload=evidence_payload,
    )
    evidence_provider = get_provider(
        settings,
        provider="fake",
        model="fake-evidence-model",
        structured_payload=evidence_payload,
    )
    explanation_provider = get_provider(
        settings,
        provider="fake",
        model="fake-explanation-model",
        structured_payload=explanation_payload,
    )
    workflow = CandidateEvaluationWorkflow(
        evidence_provider=evidence_provider,
        explanation_provider=explanation_provider,
    )
    return workflow.run(
        db,
        job_application_id=application_id,
        organization_id=organization_id,
    )
