import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.jobs import JobCreate, JobResponse, JobUpdate
from app.core.database import get_db
from app.services.job_service import JobService

router = APIRouter()


@router.post("/jobs", response_model=JobResponse, status_code=201)
def create_job(
    body: JobCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobService().create(
        db,
        organization_id=ctx.organization_id,
        title=body.title,
        raw_description=body.raw_description,
        status=body.status,
        department=body.department,
        location=body.location,
        job_type=body.job_type,
        experience=body.experience,
        requirements=body.requirements,
        required_skills=body.required_skills,
        created_by_user_id=ctx.user_id,
    )


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobService().list(db, organization_id=ctx.organization_id)


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(
    job_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    JobService().delete(db, job_id=uuid.UUID(job_id), organization_id=ctx.organization_id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobService().get(db, job_id=uuid.UUID(job_id), organization_id=ctx.organization_id)


@router.patch("/jobs/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    body: JobUpdate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobService().update(
        db,
        job_id=uuid.UUID(job_id),
        organization_id=ctx.organization_id,
        title=body.title,
        raw_description=body.raw_description,
        status=body.status,
        department=body.department,
        location=body.location,
        job_type=body.job_type,
        experience=body.experience,
        requirements=body.requirements,
        required_skills=body.required_skills,
    )
