import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models import AITrace, Organization, WorkflowRun, WorkflowStepTrace


def create_workflow_run(db_session: Session) -> WorkflowRun:
    organization = Organization(name="Workflow Org")
    db_session.add(organization)
    db_session.flush()

    workflow_run = WorkflowRun(
        organization_id=organization.id,
        workflow_type="candidate_evaluation",
        status="running",
        related_entity_type="job_application",
        related_entity_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
    )
    db_session.add(workflow_run)
    db_session.flush()

    return workflow_run


def create_workflow_step_trace(db_session: Session) -> WorkflowStepTrace:
    workflow_run = create_workflow_run(db_session)
    step_trace = WorkflowStepTrace(
        workflow_run_id=workflow_run.id,
        step_name="evaluate_candidate",
        status="running",
        started_at=datetime.now(UTC),
    )
    db_session.add(step_trace)
    db_session.flush()

    return step_trace


def test_workflow_run_can_be_created_for_organization(db_session: Session) -> None:
    workflow_run = create_workflow_run(db_session)
    db_session.commit()
    db_session.refresh(workflow_run)

    assert isinstance(workflow_run.id, uuid.UUID)
    assert workflow_run.created_at is not None
    assert workflow_run.updated_at is not None
    assert workflow_run.organization.workflow_runs == [workflow_run]


def test_workflow_run_requires_valid_organization(db_session: Session) -> None:
    db_session.add(
        WorkflowRun(
            organization_id=uuid.uuid4(),
            workflow_type="candidate_evaluation",
            status="pending",
        )
    )

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()


def test_invalid_workflow_run_status_is_rejected(db_session: Session) -> None:
    organization = Organization(name="Invalid Workflow Status Org")
    db_session.add(organization)
    db_session.flush()
    db_session.add(
        WorkflowRun(
            organization_id=organization.id,
            workflow_type="candidate_evaluation",
            status="invalid",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_invalid_workflow_related_entity_type_is_rejected(db_session: Session) -> None:
    organization = Organization(name="Invalid Related Entity Org")
    db_session.add(organization)
    db_session.flush()
    db_session.add(
        WorkflowRun(
            organization_id=organization.id,
            workflow_type="candidate_evaluation",
            status="pending",
            related_entity_type="invalid",
            related_entity_id=uuid.uuid4(),
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_workflow_step_trace_requires_valid_workflow_run(db_session: Session) -> None:
    db_session.add(
        WorkflowStepTrace(
            workflow_run_id=uuid.uuid4(),
            step_name="evaluate_candidate",
            status="pending",
        )
    )

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()


def test_workflow_step_trace_can_store_failure_details(db_session: Session) -> None:
    workflow_run = create_workflow_run(db_session)
    step_trace = WorkflowStepTrace(
        workflow_run_id=workflow_run.id,
        step_name="validate_profile",
        status="failed",
        error_type="ValidationError",
        error_message="Candidate profile did not match expected schema.",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db_session.add(step_trace)
    db_session.commit()
    db_session.refresh(step_trace)

    assert step_trace.error_type == "ValidationError"
    assert step_trace.error_message == "Candidate profile did not match expected schema."
    assert step_trace in workflow_run.step_traces


def test_invalid_workflow_step_trace_status_is_rejected(db_session: Session) -> None:
    workflow_run = create_workflow_run(db_session)
    db_session.add(
        WorkflowStepTrace(
            workflow_run_id=workflow_run.id,
            step_name="evaluate_candidate",
            status="invalid",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_ai_trace_requires_valid_workflow_step_trace(db_session: Session) -> None:
    db_session.add(
        AITrace(
            workflow_step_trace_id=uuid.uuid4(),
            ai_component_name="candidate_profile_extractor",
            status="started",
        )
    )

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()


def test_ai_trace_does_not_require_provider_or_model_name(db_session: Session) -> None:
    step_trace = create_workflow_step_trace(db_session)
    ai_trace = AITrace(
        workflow_step_trace_id=step_trace.id,
        ai_component_name="candidate_profile_extractor",
        status="started",
    )
    db_session.add(ai_trace)
    db_session.commit()
    db_session.refresh(ai_trace)

    assert isinstance(ai_trace.id, uuid.UUID)
    assert ai_trace.provider is None
    assert ai_trace.model_name is None
    assert ai_trace in step_trace.ai_traces


def test_ai_trace_can_store_schema_and_usage_metadata(db_session: Session) -> None:
    step_trace = create_workflow_step_trace(db_session)
    ai_trace = AITrace(
        workflow_step_trace_id=step_trace.id,
        ai_component_name="candidate_evaluator",
        provider="example-provider",
        model_name="example-model",
        prompt_version="candidate-evaluator-v1",
        input_schema_version="candidate-evaluation-input-v1",
        output_schema_version="candidate-evaluation-output-v1",
        status="succeeded",
        latency_ms=1200,
        input_reference={"resume_id": str(uuid.uuid4()), "input_hash": "sha256:abc123"},
        output_reference={"candidate_evaluation_id": str(uuid.uuid4())},
        token_usage={"input_tokens": 500, "output_tokens": 125},
    )
    db_session.add(ai_trace)
    db_session.commit()
    db_session.refresh(ai_trace)

    assert ai_trace.input_schema_version == "candidate-evaluation-input-v1"
    assert ai_trace.output_schema_version == "candidate-evaluation-output-v1"
    assert ai_trace.token_usage == {"input_tokens": 500, "output_tokens": 125}


def test_invalid_ai_trace_status_is_rejected(db_session: Session) -> None:
    step_trace = create_workflow_step_trace(db_session)
    db_session.add(
        AITrace(
            workflow_step_trace_id=step_trace.id,
            ai_component_name="candidate_evaluator",
            status="invalid",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_hard_deleting_workflow_run_cascades_to_step_and_ai_traces(
    db_session: Session,
) -> None:
    workflow_run = create_workflow_run(db_session)
    step_trace = WorkflowStepTrace(
        workflow_run_id=workflow_run.id,
        step_name="evaluate_candidate",
        status="completed",
    )
    db_session.add(step_trace)
    db_session.flush()
    ai_trace = AITrace(
        workflow_step_trace_id=step_trace.id,
        ai_component_name="candidate_evaluator",
        status="succeeded",
    )
    db_session.add(ai_trace)
    db_session.flush()

    workflow_run_id = workflow_run.id
    step_trace_id = step_trace.id
    ai_trace_id = ai_trace.id

    db_session.execute(delete(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
    db_session.flush()

    assert db_session.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id)) is None
    assert (
        db_session.scalar(select(WorkflowStepTrace).where(WorkflowStepTrace.id == step_trace_id))
        is None
    )
    assert db_session.scalar(select(AITrace).where(AITrace.id == ai_trace_id)) is None
