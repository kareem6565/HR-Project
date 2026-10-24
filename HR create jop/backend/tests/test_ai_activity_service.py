import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import (
    AITrace,
    Candidate,
    Job,
    Organization,
    WorkflowRun,
    WorkflowStepTrace,
)
from app.services.ai_activity_service import AIActivityService
from app.services.errors import ValidationError


def create_org_and_job(db_session: Session) -> tuple[Organization, Job]:
    organization = Organization(name="AI Activity Org")
    db_session.add(organization)
    db_session.flush()
    job = Job(
        organization_id=organization.id,
        title="Backend Developer",
        raw_description="Backend Developer job posting raw text.",
    )
    db_session.add(job)
    db_session.commit()
    return organization, job


def create_run_with_traces(
    db_session: Session,
    *,
    organization_id,
    workflow_type: str = "candidate_evaluation",
    related_entity_type: str | None = None,
    related_entity_id=None,
    status: str = "completed",
    latency_ms: int | None = 120,
) -> WorkflowRun:
    now = datetime.now(UTC)
    run = WorkflowRun(
        organization_id=organization_id,
        workflow_type=workflow_type,
        status=status,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        started_at=now - timedelta(minutes=1),
        completed_at=now,
    )
    db_session.add(run)
    db_session.flush()
    step = WorkflowStepTrace(
        workflow_run_id=run.id,
        step_name="evaluate_candidate",
        status="completed" if status == "completed" else "failed",
        started_at=run.started_at,
        completed_at=run.completed_at,
    )
    db_session.add(step)
    db_session.flush()
    db_session.add(
        AITrace(
            workflow_step_trace_id=step.id,
            ai_component_name="match_evidence_generator",
            provider="fake",
            model_name="fake-evidence-model",
            prompt_version="1",
            input_schema_version="1.1",
            output_schema_version="1.1",
            status="succeeded" if status == "completed" else "failed",
            latency_ms=latency_ms,
            input_reference={"entity": "job_application"},
        )
    )
    db_session.commit()
    return run


def test_list_runs_includes_title_labels_and_steps(db_session: Session) -> None:
    organization, job = create_org_and_job(db_session)
    run = create_run_with_traces(
        db_session,
        organization_id=organization.id,
        related_entity_type="job",
        related_entity_id=job.id,
    )
    db_session.commit()

    views = AIActivityService().list_runs(db_session, organization_id=organization.id)
    assert len(views) == 1
    view = views[0]
    assert view["id"] == run.id
    assert view["run_id"] == str(run.id)
    assert view["status"] == "success"
    assert view["title"] == "Candidate Evaluation"
    assert view["candidate_name"] is None
    assert view["job_title"] == "Backend Developer"
    assert view["provider"] == "fake"
    assert view["model"] == "fake-evidence-model"
    assert view["schema_version"] == "1.1"
    assert view["prompt"] == "1"
    step_names = [step["name"] for step in view["steps"]]
    assert "Evaluate Candidate" in step_names
    assert "Generate Match Evidence" in step_names


def test_list_runs_scoped_to_org(db_session: Session) -> None:
    organization, _job = create_org_and_job(db_session)
    create_run_with_traces(db_session, organization_id=organization.id)
    other_org = Organization(name="Other Org")
    db_session.add(other_org)
    db_session.commit()

    views = AIActivityService().list_runs(db_session, organization_id=other_org.id)
    assert views == []


def test_list_runs_resolves_candidate_name(db_session: Session) -> None:
    organization, _job = create_org_and_job(db_session)
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Omar Adel",
        email="omar@example.com",
    )
    db_session.add(candidate)
    db_session.commit()
    create_run_with_traces(
        db_session,
        organization_id=organization.id,
        related_entity_type="candidate",
        related_entity_id=candidate.id,
    )
    db_session.commit()

    views = AIActivityService().list_runs(db_session, organization_id=organization.id)
    assert views[0]["candidate_name"] == "Omar Adel"


def test_stats_counts_successes_failures_and_latency(db_session: Session) -> None:
    organization, _job = create_org_and_job(db_session)
    create_run_with_traces(
        db_session,
        organization_id=organization.id,
        status="completed",
        latency_ms=100,
    )
    create_run_with_traces(
        db_session,
        organization_id=organization.id,
        status="failed",
        latency_ms=None,
    )
    db_session.commit()

    stats = AIActivityService().get_stats(db_session, organization_id=organization.id)
    assert stats["total_runs_24h"] == 2
    assert stats["successful"] == 1
    assert stats["failed"] == 1
    assert stats["avg_latency_ms"] == 100


def test_stats_only_include_last_24h(db_session: Session) -> None:
    organization, _job = create_org_and_job(db_session)
    now = datetime.now(UTC)
    old_run = WorkflowRun(
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="completed",
        created_at=now - timedelta(days=2),
        started_at=now - timedelta(days=2),
        completed_at=now - timedelta(days=2) + timedelta(minutes=1),
    )
    db_session.add(old_run)
    db_session.commit()

    stats = AIActivityService().get_stats(db_session, organization_id=organization.id)
    assert stats["total_runs_24h"] == 0


def test_retry_rejects_non_failed_run(db_session: Session) -> None:
    organization, _job = create_org_and_job(db_session)
    run = create_run_with_traces(
        db_session,
        organization_id=organization.id,
        status="completed",
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="Only failed workflow runs"):
        AIActivityService().retry_run(
            db_session,
            organization_id=organization.id,
            workflow_run_id=run.id,
        )


def test_retry_rejects_other_org(db_session: Session) -> None:
    organization, _job = create_org_and_job(db_session)
    run = create_run_with_traces(
        db_session,
        organization_id=organization.id,
        status="failed",
    )
    other_org = Organization(name="Other Org")
    db_session.add(other_org)
    db_session.commit()

    with pytest.raises(ValidationError, match="different organization"):
        AIActivityService().retry_run(
            db_session,
            organization_id=other_org.id,
            workflow_run_id=run.id,
        )


def test_retry_reruns_failed_job_profile_extraction(db_session: Session) -> None:
    organization, job = create_org_and_job(db_session)
    failed_run = create_run_with_traces(
        db_session,
        organization_id=organization.id,
        workflow_type="job_profile_extraction",
        related_entity_type="job",
        related_entity_id=job.id,
        status="failed",
    )
    db_session.commit()

    result = AIActivityService().retry_run(
        db_session,
        organization_id=organization.id,
        workflow_run_id=failed_run.id,
    )
    db_session.commit()

    assert result["status"] == "running"
    new_run = db_session.get(WorkflowRun, result["run_id"])
    assert new_run is not None
    assert new_run.workflow_type == "job_profile_extraction"
    assert new_run.related_entity_id == job.id
    assert new_run.status == "completed"


def test_retry_rejects_unrelated_entity_type(db_session: Session) -> None:
    organization, _job = create_org_and_job(db_session)
    run = create_run_with_traces(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        related_entity_type="job",
        related_entity_id=uuid.uuid4(),
        status="failed",
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="job_application"):
        AIActivityService().retry_run(
            db_session,
            organization_id=organization.id,
            workflow_run_id=run.id,
        )
