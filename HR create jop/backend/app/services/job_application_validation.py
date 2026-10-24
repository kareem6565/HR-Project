from app.models.candidate import Candidate
from app.models.job import Job
from app.models.resume import Resume
from app.services.errors import NotFoundError, ValidationError


def validate_job_application_consistency(
    *,
    organization_id: object,
    job: Job,
    candidate: Candidate,
    resume: Resume,
) -> None:
    if job.organization_id != organization_id:
        raise ValidationError("Job must belong to the same organization as the application.")

    if candidate.organization_id != organization_id:
        raise ValidationError("Candidate must belong to the same organization as the application.")

    if resume.candidate.organization_id != organization_id:
        raise ValidationError("Resume must belong to the same organization as the application.")

    if resume.candidate_id != candidate.id:
        raise ValidationError("Resume must belong to the job application's candidate.")
