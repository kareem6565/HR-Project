import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AITrace,
    Candidate,
    Job,
    JobApplication,
    Organization,
    Resume,
    User,
    WorkflowRun,
    WorkflowStepTrace,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.observability_service import ObservabilityService
from app.services.workflow_trace_service import WorkflowTraceService


def create_organization(db_session: Session) -> Organization:
    organization = Organization(name="Observability Org")
    db_session.add(organization)
    db_session.flush()
    return organization


def create_application(db_session: Session, organization: Organization) -> JobApplication:
    user = User(
        organization_id=organization.id,
        email="obs-service@example.com",
        full_name="Observability User",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Observability Candidate",
        email="obs-candidate@example.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()
    job = Job(organization_id=organization.id, created_by_user_id=user.id, title="ML Engineer")
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/obs.pdf")
    db_session.add_all([job, resume])
    db_session.flush()
    application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    db_session.add(application)
    db_session.flush()
    return application


def seed_successful_run(db_session: Session) -> tuple[WorkflowRun, WorkflowStepTrace, AITrace]:
    """Create a completed run with one succeeded AI trace via the real service."""
    organization = create_organization(db_session)
    application = create_application(db_session, organization)
    trace_service = WorkflowTraceService()
    run = trace_service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        related_entity_type="job_application",
        related_entity_id=application.id,
        status="running",
    )
    step = trace_service.start_step(
        db_session,
        workflow_run_id=run.id,
        step_name="evaluate_candidate",
    )
    ai_trace = trace_service.record_ai_trace(
        db_session,
        workflow_step_trace_id=step.id,
        ai_component_name="match_evidence_generator",
        status="succeeded",
        provider="fake",
        model_name="fake-model",
        prompt_version="1",
        input_schema_version="1.0",
        output_schema_version="1.0",
        latency_ms=120,
        input_reference={
            "entity": "job_application",
            "entity_id": str(uuid.uuid4()),
            "job_profile_sha256": "a" * 64,
        },
        output_reference={"output_sha256": "b" * 64},
        token_usage={"input_tokens": 10, "output_tokens": 5},
    )
    trace_service.mark_step_completed(db_session, workflow_step_trace_id=step.id)
    trace_service.mark_run_completed(db_session, workflow_run_id=run.id)
    db_session.commit()
    return run, step, ai_trace


def create_run_with_timestamps(
    db_session: Session,
    *,
    started_at: datetime,
    completed_at: datetime,
    status: str = "completed",
) -> WorkflowRun:
    organization = create_organization(db_session)
    run = WorkflowRun(
        organization_id=organization.id,
        workflow_type="candidate_profile_extraction",
        status=status,
        related_entity_type="resume",
        related_entity_id=uuid.uuid4(),
        started_at=started_at,
        completed_at=completed_at,
    )
    db_session.add(run)
    db_session.flush()
    return run


def test_get_workflow_run_by_id(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    found = service.get_workflow_run(
        db_session, workflow_run_id=run.id, organization_id=run.organization_id
    )

    assert found.id == run.id
    assert found.workflow_type == "candidate_evaluation"
    assert found.status == "completed"


def test_missing_workflow_run(db_session: Session) -> None:
    service = ObservabilityService()

    with pytest.raises(NotFoundError, match="WorkflowRun was not found"):
        service.get_workflow_run(db_session, workflow_run_id=uuid.uuid4())


def test_organization_isolation(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    other_org = Organization(name="Other Org")
    db_session.add(other_org)
    db_session.commit()
    service = ObservabilityService()

    with pytest.raises(ValidationError, match="different organization"):
        service.get_workflow_run(db_session, workflow_run_id=run.id, organization_id=other_org.id)

    with pytest.raises(ValidationError, match="different organization"):
        service.list_workflow_steps(
            db_session, workflow_run_id=run.id, organization_id=other_org.id
        )

    with pytest.raises(ValidationError, match="different organization"):
        service.list_ai_traces(db_session, workflow_run_id=run.id, organization_id=other_org.id)


def test_list_workflow_steps(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    steps = service.list_workflow_steps(db_session, workflow_run_id=run.id)

    assert len(steps) == 1
    assert steps[0].step_name == "evaluate_candidate"
    assert steps[0].status == "completed"


def test_list_ai_traces_for_step(db_session: Session) -> None:
    _run, step, ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    traces = service.list_ai_traces(db_session, workflow_step_trace_id=step.id)

    assert [trace.id for trace in traces] == [ai_trace.id]
    assert traces[0].ai_component_name == "match_evidence_generator"


def test_list_ai_traces_for_workflow(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    traces = service.list_ai_traces(db_session, workflow_run_id=run.id)

    assert len(traces) == 1
    assert traces[0].status == "succeeded"


def test_list_ai_traces_requires_scope(db_session: Session) -> None:
    _run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    with pytest.raises(ValidationError, match="Either workflow_run_id"):
        service.list_ai_traces(db_session)


def test_completed_workflow_duration(db_session: Session) -> None:
    started_at = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    completed_at = datetime(2026, 1, 1, 10, 0, 30, tzinfo=UTC)
    run = create_run_with_timestamps(db_session, started_at=started_at, completed_at=completed_at)
    db_session.commit()
    service = ObservabilityService()

    summary = service.get_workflow_summary(db_session, workflow_run_id=run.id)

    assert summary.duration_seconds == 30.0


def test_completed_step_duration(db_session: Session) -> None:
    run = create_run_with_timestamps(
        db_session,
        started_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, 10, 0, 30, tzinfo=UTC),
    )
    step = WorkflowStepTrace(
        workflow_run_id=run.id,
        step_name="extract_candidate_profile",
        status="completed",
        started_at=datetime(2026, 1, 1, 10, 0, 5, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, 10, 0, 15, tzinfo=UTC),
    )
    db_session.add(step)
    db_session.commit()
    service = ObservabilityService()

    summary = service.get_workflow_summary(db_session, workflow_run_id=run.id)
    assert summary.duration_seconds == 30.0


def test_ai_latency_exposed(db_session: Session) -> None:
    run, _step, ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    traces = service.list_ai_traces(db_session, workflow_run_id=run.id)

    assert traces[0].latency_ms == 120
    assert traces[0].id == ai_trace.id


def test_running_workflow_handled_safely(db_session: Session) -> None:
    run = create_run_with_timestamps(
        db_session,
        started_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        completed_at=None,
        status="running",
    )
    db_session.commit()
    service = ObservabilityService()

    summary = service.get_workflow_summary(db_session, workflow_run_id=run.id)

    assert summary.status == "running"
    assert summary.completed_at is None
    assert summary.duration_seconds is None


def test_failed_workflows_query(db_session: Session) -> None:
    create_organization(db_session)
    service = ObservabilityService()
    org = db_session.scalar(select(Organization).limit(1))
    trace_service = WorkflowTraceService()
    rejected = trace_service.start_run(
        db_session,
        organization_id=org.id,
        workflow_type="candidate_evaluation",
        status="running",
    )
    trace_service.mark_run_failed(db_session, workflow_run_id=rejected.id)
    accepted = trace_service.start_run(
        db_session,
        organization_id=org.id,
        workflow_type="job_profile_extraction",
        status="running",
    )
    trace_service.mark_run_completed(db_session, workflow_run_id=accepted.id)
    db_session.commit()

    failed = service.get_failed_workflows(db_session, organization_id=org.id)

    assert [run.id for run in failed] == [rejected.id]
    assert failed[0].status == "failed"


def test_failed_workflows_filtered_by_type(db_session: Session) -> None:
    org = create_organization(db_session)
    service = ObservabilityService()
    trace_service = WorkflowTraceService()
    run_a = trace_service.start_run(
        db_session, organization_id=org.id, workflow_type="candidate_evaluation", status="running"
    )
    trace_service.mark_run_failed(db_session, workflow_run_id=run_a.id)
    run_b = trace_service.start_run(
        db_session, organization_id=org.id, workflow_type="job_profile_extraction", status="running"
    )
    trace_service.mark_run_failed(db_session, workflow_run_id=run_b.id)
    db_session.commit()

    failed = service.get_failed_workflows(
        db_session, organization_id=org.id, workflow_type="job_profile_extraction"
    )

    assert [run.id for run in failed] == [run_b.id]


def test_failed_ai_trace_query(db_session: Session) -> None:
    org = create_organization(db_session)
    trace_service = WorkflowTraceService()
    run = trace_service.start_run(
        db_session, organization_id=org.id, workflow_type="candidate_evaluation", status="running"
    )
    step = trace_service.start_step(
        db_session, workflow_run_id=run.id, step_name="evaluate_candidate"
    )
    failed_trace = trace_service.record_ai_trace(
        db_session,
        workflow_step_trace_id=step.id,
        ai_component_name="match_evidence_generator",
        status="failed",
        prompt_version="1",
        input_schema_version="1.0",
        output_schema_version="1.0",
    )
    trace_service.mark_step_failed(
        db_session,
        workflow_step_trace_id=step.id,
        error_type="ProviderTimeoutError",
        error_message="timed out",
    )
    trace_service.mark_run_failed(db_session, workflow_run_id=run.id)
    db_session.commit()
    service = ObservabilityService()

    summary = service.get_ai_failure_summary(db_session, organization_id=org.id)
    assert summary.failed == 1
    assert summary.succeeded == 0
    assert summary.total == 1

    runs = service.get_failed_workflows(db_session, organization_id=org.id)
    assert [r.id for r in runs] == [run.id]
    steps = service.list_workflow_steps(db_session, workflow_run_id=run.id)
    assert steps[0].error_type == "ProviderTimeoutError"
    ai_traces = service.list_ai_traces(db_session, workflow_run_id=run.id)
    assert ai_traces[0].status == "failed"
    assert ai_traces[0].id == failed_trace.id


def test_validation_failed_trace_distinguishable(db_session: Session) -> None:
    org = create_organization(db_session)
    trace_service = WorkflowTraceService()
    run = trace_service.start_run(
        db_session, organization_id=org.id, workflow_type="candidate_evaluation", status="running"
    )
    step = trace_service.start_step(
        db_session, workflow_run_id=run.id, step_name="evaluate_candidate"
    )
    trace_service.record_ai_trace(
        db_session,
        workflow_step_trace_id=step.id,
        ai_component_name="match_evidence_generator",
        status="validation_failed",
        provider="fake",
        model_name="fake-model",
        prompt_version="1",
        input_schema_version="1.0",
        output_schema_version="1.0",
        validation_error={"schema": "1.0", "message": "invalid"},
    )
    trace_service.mark_step_failed(
        db_session,
        workflow_step_trace_id=step.id,
        error_type="ValidationError",
        error_message="Invalid AI output contract",
    )
    trace_service.mark_run_failed(db_session, workflow_run_id=run.id)
    db_session.commit()
    service = ObservabilityService()

    summary = service.get_ai_failure_summary(db_session, organization_id=org.id)
    assert summary.validation_failed == 1
    assert summary.failed == 0

    ai_traces = service.list_ai_traces(db_session, workflow_run_id=run.id)
    assert ai_traces[0].status == "validation_failed"
    assert ai_traces[0].validation_error == {"schema": "1.0", "message": "invalid"}


def test_provider_and_model_visible(db_session: Session) -> None:
    run, _step, ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    found = service.get_ai_trace(db_session, ai_trace_id=ai_trace.id)
    assert found.provider == "fake"
    assert found.model_name == "fake-model"


def test_promptand_schema_versions_visible(db_session: Session) -> None:
    run, _step, ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    traces = service.list_ai_traces(db_session, workflow_run_id=run.id)
    assert traces[0].prompt_version == "1"
    assert traces[0].input_schema_version == "1.0"
    assert traces[0].output_schema_version == "1.0"
    assert traces[0].token_usage == {"input_tokens": 10, "output_tokens": 5}


def test_input_and_output_references_available(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    trace = service.list_ai_traces(db_session, workflow_run_id=run.id)[0]
    assert trace.input_reference["entity"] == "job_application"
    assert trace.input_reference["job_profile_sha256"] == "a" * 64
    assert trace.output_reference["output_sha256"] == "b" * 64


def test_hashes_available(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    trace = service.list_ai_traces(db_session, workflow_run_id=run.id)[0]
    sha_in = trace.input_reference["job_profile_sha256"]
    sha_out = trace.output_reference["output_sha256"]
    assert len(sha_in) == 64
    assert len(sha_out) == 64
    int(sha_in, 16)
    int(sha_out, 16)


def test_related_entity_visible(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    summary = service.get_workflow_summary(db_session, workflow_run_id=run.id)
    assert summary.related_entity_type == "job_application"
    assert summary.related_entity_id is not None


def test_raw_resume_text_not_exposed(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    traces = service.list_ai_traces(db_session, workflow_run_id=run.id)
    trace = traces[0]
    raw = "Ada Lovelace worked at a private analytical engine company in 1843."
    assert raw not in str(trace.input_reference or {})
    assert raw not in str(trace.output_reference or {})
    assert not hasattr(trace, "raw_text")


def test_raw_job_description_not_exposed(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    traces = service.list_ai_traces(db_session, workflow_run_id=run.id)
    trace = traces[0]
    raw = "We are hiring a senior machine learning engineer with 8 years of experience."
    assert raw not in str(trace.input_reference or {})
    assert raw not in str(trace.output_reference or {})


def test_raw_prompt_not_exposed(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    traces = service.list_ai_traces(db_session, workflow_run_id=run.id)
    trace = traces[0]
    raw = "You are an expert recruiter. Analyze the following resume and job description."
    assert raw not in str(trace.input_reference or {})
    assert raw not in str(trace.output_reference or {})
    assert not hasattr(trace, "raw_prompt")


def test_raw_model_output_not_exposed(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    traces = service.list_ai_traces(db_session, workflow_run_id=run.id)
    trace = traces[0]
    raw = '{"summary": "This candidate is an excellent fit for the role."}'
    assert raw not in str(trace.input_reference or {})
    assert raw not in str(trace.output_reference or {})
    assert not hasattr(trace, "full_output")


def test_queries_do_not_create_or_modify_traces(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()

    counts_before = count_rows(db_session, AITrace)
    db_session.expire_all()

    service.get_workflow_run(db_session, workflow_run_id=run.id)
    service.list_workflow_steps(db_session, workflow_run_id=run.id)
    service.list_ai_traces(db_session, workflow_run_id=run.id)
    service.get_workflow_summary(db_session, workflow_run_id=run.id)
    service.get_failed_workflows(db_session)
    service.get_ai_failure_summary(db_session)
    db_session.flush()

    assert count_rows(db_session, AITrace) == counts_before
    trace = service.get_ai_trace(db_session, ai_trace_id=_ai_trace.id)
    db_session.refresh(trace)
    assert trace.status == "succeeded"
    assert trace.latency_ms == 120


def test_no_domain_artifacts_modified(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()
    db_session.commit()
    before = {
        "run": db_session.get(WorkflowRun, run.id).status,
    }
    db_session.expire_all()

    service.get_workflow_summary(db_session, workflow_run_id=run.id)

    assert db_session.get(WorkflowRun, run.id).status == before["run"]
    assert count_rows(db_session, WorkflowStepTrace) == 1


def test_queries_do_not_commit(db_session: Session) -> None:
    run, _step, _ai_trace = seed_successful_run(db_session)
    service = ObservabilityService()
    db_session.expire_all()

    service.get_workflow_run(db_session, workflow_run_id=run.id)
    service.get_workflow_summary(db_session, workflow_run_id=run.id)
    service.get_failed_workflows(db_session)
    service.get_ai_failure_summary(db_session)

    assert db_session.is_active
    assert not db_session.new
    assert not db_session.dirty
    assert count_rows(db_session, AITrace) == 1
    assert count_rows(db_session, WorkflowRun) == 1


def test_ai_failure_summary_across_statuses(db_session: Session) -> None:
    org = create_organization(db_session)
    trace_service = WorkflowTraceService()
    run = trace_service.start_run(
        db_session, organization_id=org.id, workflow_type="candidate_evaluation", status="running"
    )
    step = trace_service.start_step(
        db_session, workflow_run_id=run.id, step_name="evaluate_candidate"
    )
    trace_service.record_ai_trace(
        db_session,
        workflow_step_trace_id=step.id,
        ai_component_name="a",
        status="succeeded",
    )
    trace_service.record_ai_trace(
        db_session,
        workflow_step_trace_id=step.id,
        ai_component_name="b",
        status="failed",
    )
    trace_service.record_ai_trace(
        db_session,
        workflow_step_trace_id=step.id,
        ai_component_name="c",
        status="validation_failed",
    )
    trace_service.mark_step_completed(db_session, workflow_step_trace_id=step.id)
    trace_service.mark_run_completed(db_session, workflow_run_id=run.id)
    db_session.commit()
    service = ObservabilityService()

    summary = service.get_ai_failure_summary(db_session, organization_id=org.id)
    assert summary.succeeded == 1
    assert summary.failed == 1
    assert summary.validation_failed == 1
    assert summary.total == 3


def count_rows(db_session: Session, model) -> int:
    return db_session.scalar(select(func.count()).select_from(model))
