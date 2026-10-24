import uuid

import pytest
from sqlalchemy.orm import Session

from app.models import Candidate, Job, Organization
from app.services.errors import NotFoundError, ValidationError
from app.services.workflow_trace_service import WorkflowTraceService


def create_organization(db_session: Session) -> Organization:
    organization = Organization(name="Workflow Service Org")
    db_session.add(organization)
    db_session.flush()
    return organization


def create_job(db_session: Session, organization: Organization) -> Job:
    job = Job(organization_id=organization.id, title="Workflow Job")
    db_session.add(job)
    db_session.flush()
    return job


def test_start_run(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()

    run = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="running",
    )
    db_session.commit()
    db_session.refresh(run)

    assert run.workflow_type == "candidate_evaluation"
    assert run.status == "running"
    assert run.started_at is not None
    assert isinstance(run.id, uuid.UUID)


def test_start_run_with_related_entity(db_session: Session) -> None:
    organization = create_organization(db_session)
    job = create_job(db_session, organization)
    service = WorkflowTraceService()

    run = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="job_profile_extraction",
        related_entity_type="job",
        related_entity_id=job.id,
        status="pending",
    )
    db_session.commit()

    assert run.related_entity_type == "job"
    assert run.related_entity_id == job.id
    assert run.started_at is None


def test_invalid_start_run_status_rejected(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()

    with pytest.raises(ValidationError, match="must start as pending or running"):
        service.start_run(
            db_session,
            organization_id=organization.id,
            workflow_type="candidate_evaluation",
            status="completed",
        )


def test_missing_organization_rejected(db_session: Session) -> None:
    service = WorkflowTraceService()

    with pytest.raises(NotFoundError, match="Organization was not found"):
        service.start_run(
            db_session,
            organization_id=uuid.uuid4(),
            workflow_type="candidate_evaluation",
        )


def test_valid_run_state_transitions(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()
    run = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="pending",
    )
    db_session.commit()

    service.mark_run_running(db_session, workflow_run_id=run.id)
    db_session.commit()
    db_session.refresh(run)
    assert run.status == "running"

    service.mark_run_waiting_for_human(db_session, workflow_run_id=run.id)
    db_session.commit()
    db_session.refresh(run)
    assert run.status == "waiting_for_human"

    service.mark_run_completed(db_session, workflow_run_id=run.id)
    db_session.commit()
    db_session.refresh(run)
    assert run.status == "completed"
    assert run.completed_at is not None


def test_mark_run_failed_and_cancelled(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()
    run = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="running",
    )
    db_session.commit()

    service.mark_run_failed(db_session, workflow_run_id=run.id)
    db_session.commit()
    db_session.refresh(run)
    assert run.status == "failed"

    run2 = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="pending",
    )
    db_session.commit()
    service.mark_run_cancelled(db_session, workflow_run_id=run2.id)
    db_session.commit()
    db_session.refresh(run2)
    assert run2.status == "cancelled"


def test_start_step(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()
    run = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="running",
    )
    db_session.commit()

    step = service.start_step(
        db_session,
        workflow_run_id=run.id,
        step_name="evaluate_candidate",
        status="running",
    )
    db_session.commit()
    db_session.refresh(step)

    assert step.step_name == "evaluate_candidate"
    assert step.status == "running"
    assert isinstance(step.id, uuid.UUID)


def test_invalid_step_status_rejected(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()
    run = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="running",
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="must start as pending or running"):
        service.start_step(
            db_session,
            workflow_run_id=run.id,
            step_name="evaluate_candidate",
            status="completed",
        )


def test_mark_step_completed_failed_skipped(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()
    run = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="running",
    )
    db_session.commit()
    completed_step = service.start_step(
        db_session, workflow_run_id=run.id, step_name="step_a", status="running"
    )
    failed_step = service.start_step(
        db_session, workflow_run_id=run.id, step_name="step_b", status="running"
    )
    skipped_step = service.start_step(
        db_session, workflow_run_id=run.id, step_name="step_c", status="pending"
    )
    db_session.commit()

    service.mark_step_completed(db_session, workflow_step_trace_id=completed_step.id)
    service.mark_step_failed(
        db_session,
        workflow_step_trace_id=failed_step.id,
        error_type="ValidationError",
        error_message="Bad data",
    )
    service.mark_step_skipped(db_session, workflow_step_trace_id=skipped_step.id)
    db_session.commit()

    db_session.refresh(completed_step)
    db_session.refresh(failed_step)
    db_session.refresh(skipped_step)
    assert completed_step.status == "completed"
    assert failed_step.status == "failed"
    assert failed_step.error_type == "ValidationError"
    assert failed_step.error_message == "Bad data"
    assert skipped_step.status == "skipped"


def test_invalid_related_entity_type_rejected(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()

    with pytest.raises(ValidationError, match="not supported"):
        service.start_run(
            db_session,
            organization_id=organization.id,
            workflow_type="candidate_evaluation",
            related_entity_type="invalid",
            related_entity_id=uuid.uuid4(),
        )


def test_missing_related_entity_rejected(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()

    with pytest.raises(NotFoundError, match="related entity was not found"):
        service.start_run(
            db_session,
            organization_id=organization.id,
            workflow_type="candidate_evaluation",
            related_entity_type="job",
            related_entity_id=uuid.uuid4(),
        )


def test_related_entity_type_without_id_rejected(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()

    with pytest.raises(ValidationError, match="supplied together"):
        service.start_run(
            db_session,
            organization_id=organization.id,
            workflow_type="candidate_evaluation",
            related_entity_type="job",
            related_entity_id=None,
        )


def test_cross_organization_related_entity_rejected(db_session: Session) -> None:
    organization_a = create_organization(db_session)
    organization_b = Organization(name="Other Workflow Org")
    db_session.add(organization_b)
    db_session.flush()
    job_in_b = create_job(db_session, organization_b)
    db_session.commit()
    service = WorkflowTraceService()

    with pytest.raises(ValidationError, match="different organization"):
        service.start_run(
            db_session,
            organization_id=organization_a.id,
            workflow_type="job_profile_extraction",
            related_entity_type="job",
            related_entity_id=job_in_b.id,
        )


def test_candidate_related_entity_scoping(db_session: Session) -> None:
    organization = create_organization(db_session)
    other_organization = Organization(name="Other Candidate Org")
    db_session.add(other_organization)
    db_session.flush()
    candidate = Candidate(organization_id=other_organization.id, full_name="Other Candidate")
    db_session.add(candidate)
    db_session.commit()
    service = WorkflowTraceService()

    with pytest.raises(ValidationError, match="different organization"):
        service.start_run(
            db_session,
            organization_id=organization.id,
            workflow_type="candidate_profile_extraction",
            related_entity_type="candidate",
            related_entity_id=candidate.id,
        )


def test_record_ai_trace(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()
    run = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="running",
    )
    db_session.commit()
    step = service.start_step(
        db_session, workflow_run_id=run.id, step_name="evaluate_candidate", status="running"
    )
    db_session.commit()

    trace = service.record_ai_trace(
        db_session,
        workflow_step_trace_id=step.id,
        ai_component_name="candidate_evaluator",
        status="succeeded",
        provider="example-provider",
        model_name="example-model",
        prompt_version="evaluator-v1",
        input_schema_version="eval-input-v1",
        output_schema_version="eval-output-v1",
        latency_ms=1200,
        input_reference={"resume_id": str(uuid.uuid4()), "input_hash": "sha256:abc123"},
        output_reference={"candidate_evaluation_id": str(uuid.uuid4())},
        token_usage={"input_tokens": 500, "output_tokens": 125},
    )
    db_session.commit()
    db_session.refresh(trace)

    assert trace.ai_component_name == "candidate_evaluator"
    assert trace.status == "succeeded"
    assert trace.provider == "example-provider"
    assert trace.model_name == "example-model"
    assert trace.prompt_version == "evaluator-v1"
    assert trace.input_schema_version == "eval-input-v1"
    assert trace.output_schema_version == "eval-output-v1"
    assert trace.latency_ms == 1200
    assert trace in step.ai_traces


def test_ai_trace_validation_error_metadata(db_session: Session) -> None:
    organization = create_organization(db_session)
    service = WorkflowTraceService()
    run = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="running",
    )
    db_session.commit()
    step = service.start_step(
        db_session, workflow_run_id=run.id, step_name="evaluate_candidate", status="running"
    )
    db_session.commit()

    trace = service.record_ai_trace(
        db_session,
        workflow_step_trace_id=step.id,
        ai_component_name="candidate_evaluator",
        status="validation_failed",
        validation_error={"schema": "eval-output-v1", "field": "score", "message": "Missing"},
    )
    db_session.commit()
    db_session.refresh(trace)

    assert trace.status == "validation_failed"
    assert trace.validation_error == {
        "schema": "eval-output-v1",
        "field": "score",
        "message": "Missing",
    }


def test_ai_trace_does_not_persist_raw_payloads(db_session: Session) -> None:
    """AITrace must store only references/hashes/metadata, never raw CV text or prompts."""
    organization = create_organization(db_session)
    service = WorkflowTraceService()
    run = service.start_run(
        db_session,
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="running",
    )
    db_session.commit()
    step = service.start_step(
        db_session, workflow_run_id=run.id, step_name="evaluate_candidate", status="running"
    )
    db_session.commit()
    service.record_ai_trace(
        db_session,
        workflow_step_trace_id=step.id,
        ai_component_name="candidate_evaluator",
        status="succeeded",
        input_reference={"input_hash": "sha256:feedface"},  # reference/hash only
        output_reference={"candidate_evaluation_id": str(uuid.uuid4())},  # reference only
    )
    db_session.commit()

    trace = step.ai_traces[0]
    assert trace.input_reference == {"input_hash": "sha256:feedface"}
    assert "raw" not in trace.input_reference
    assert "text" not in trace.input_reference
    # The trace object exposes no raw CV/prompt/output storage columns.
    assert not hasattr(trace, "raw_text")
    assert not hasattr(trace, "raw_prompt")
    assert not hasattr(trace, "full_output")
