"""Tests for the HERA assistant agent workflow (plan -> tools -> compose)."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.contracts import AI_CONTRACT_SCHEMA_VERSION
from app.ai.providers.errors import ProviderTimeoutError
from app.ai.providers.factory import get_provider
from app.ai.providers.fake import FakeAIProvider
from app.ai.workflows import HERAAssistantWorkflow, HERAToolInvocation
from app.core.config import Settings
from app.models import AITrace, ChatThread, Organization, User, WorkflowRun, WorkflowStepTrace
from app.services.errors import NotFoundError, ValidationError


def create_org_user_thread(
    db_session: Session,
) -> tuple[Organization, User, ChatThread]:
    organization = Organization(name="HERA Assistant Org")
    db_session.add(organization)
    db_session.flush()
    user = User(
        organization_id=organization.id,
        email="hera-assistant@example.com",
        full_name="HERA Assistant User",
    )
    thread = ChatThread(organization_id=organization.id, title="HERA test thread")
    db_session.add_all([user, thread])
    db_session.flush()
    return organization, user, thread


def plan_payload(*tool_calls: dict) -> dict:
    return {
        "schema_version": AI_CONTRACT_SCHEMA_VERSION,
        "tool_calls": list(tool_calls),
    }


def reply_payload(answer: str = "Grounded answer.", used_indices: list[int] | None = None) -> dict:
    return {
        "schema_version": AI_CONTRACT_SCHEMA_VERSION,
        "answer": answer,
        "used_tool_indices": used_indices or [],
        "links": [],
    }


def make_plan_provider(*tool_calls: dict, failure=None) -> FakeAIProvider:
    return FakeAIProvider(
        provider="fake",
        model="fake-hera-planner",
        structured_payload=plan_payload(*tool_calls),
        token_usage={"input_tokens": 10, "output_tokens": 10},
        latency_ms=20,
        failure=failure,
    )


def make_compose_factory(
    *,
    failure=None,
    capture=None,
) -> callable:
    def factory(invocations):
        if capture is not None:
            capture.append(list(invocations))
        if failure is not None:
            return FakeAIProvider(
                provider="fake",
                model="fake-hera-composer",
                failure=failure,
            )
        indices = [i for i, invocation in enumerate(invocations) if invocation.ok]
        return FakeAIProvider(
            provider="fake",
            model="fake-hera-composer",
            structured_payload=reply_payload("Grounded answer.", indices),
        )

    return factory


def count_rows(db_session: Session, model) -> int:
    return db_session.scalar(select(func.count()).select_from(model))


def test_success_runs_tool_and_records_completed_traces(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()

    result = workflow.run(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
        chat_thread_id=thread.id,
        user_message="What is the pipeline status?",
        history_text="[]",
        plan_provider=make_plan_provider(
            {"tool": "summarize_pipeline", "arguments": {"status": "advanced"}}
        ),
        compose_provider_factory=make_compose_factory(),
    )
    db_session.commit()

    assert len(result.invocations) == 1
    assert result.invocations[0].tool == "summarize_pipeline"
    assert result.invocations[0].ok is True
    assert "total" in result.invocations[0].data
    assert result.reply.answer == "Grounded answer."
    assert result.reply.used_tool_indices == [0]

    run = db_session.get(WorkflowRun, result.workflow_run_id)
    assert run.status == "completed"
    assert run.workflow_type == "hera_assistant"
    assert run.related_entity_type == "chat_thread"
    assert run.related_entity_id == thread.id

    plan_step = db_session.get(WorkflowStepTrace, result.plan_step_id)
    compose_step = db_session.get(WorkflowStepTrace, result.compose_step_id)
    assert plan_step.step_name == "plan_and_execute_tools"
    assert plan_step.status == "completed"
    assert compose_step.step_name == "compose_reply"
    assert compose_step.status == "completed"

    plan_trace = db_session.get(AITrace, result.plan_ai_trace_id)
    compose_trace = db_session.get(AITrace, result.compose_ai_trace_id)
    assert plan_trace.status == "succeeded"
    assert compose_trace.status == "succeeded"
    assert plan_trace.provider == "fake"
    assert compose_trace.provider == "fake"


def test_empty_plan_runs_no_tools(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()

    result = workflow.run(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
        chat_thread_id=thread.id,
        user_message="Hello HERA",
        history_text="[]",
        plan_provider=make_plan_provider(),
        compose_provider_factory=make_compose_factory(),
    )
    db_session.commit()

    assert result.invocations == []
    assert result.reply.answer == "Grounded answer."
    assert result.reply.used_tool_indices == []


def test_compose_factory_receives_executed_invocations(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()
    captured: list = []

    result = workflow.run(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
        chat_thread_id=thread.id,
        user_message="talent pool",
        history_text="[]",
        plan_provider=make_plan_provider({"tool": "get_talent_pool", "arguments": {}}),
        compose_provider_factory=make_compose_factory(capture=captured),
    )
    db_session.commit()

    assert len(captured) == 1
    invocations = captured[0]
    assert isinstance(invocations[0], HERAToolInvocation)
    assert invocations[0].tool == "get_talent_pool"
    assert invocations[0].ok is True
    assert result.invocations[0].data is invocations[0].data


def test_unauthorized_tool_is_reported_but_run_completes(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()

    result = workflow.run(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
        chat_thread_id=thread.id,
        user_message="do something bad",
        history_text="[]",
        plan_provider=make_plan_provider({"tool": "drop_database", "arguments": {}}),
        compose_provider_factory=make_compose_factory(),
    )
    db_session.commit()

    assert len(result.invocations) == 1
    assert result.invocations[0].ok is False
    assert "not an authorized tool" in result.invocations[0].error
    run = db_session.get(WorkflowRun, result.workflow_run_id)
    assert run.status == "completed"


def test_invalid_arguments_are_isolated(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()

    result = workflow.run(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
        chat_thread_id=thread.id,
        user_message="pipeline",
        history_text="[]",
        plan_provider=make_plan_provider(
            {"tool": "summarize_pipeline", "arguments": {"status": "not-a-status"}}
        ),
        compose_provider_factory=make_compose_factory(),
    )
    db_session.commit()

    assert result.invocations[0].ok is False
    assert "must be one of" in result.invocations[0].error
    assert db_session.get(WorkflowRun, result.workflow_run_id).status == "completed"


def test_non_scalar_argument_rejected_at_contract(db_session: Session) -> None:
    """Non-scalar plan arguments are already rejected by the plan contract.

    The argument authorization gate in the registry is the second layer; the
    contract itself forbids non-scalar argument values first.
    """
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()

    with pytest.raises(ValidationError, match="Invalid AI output contract"):
        workflow.run(
            db_session,
            organization_id=organization.id,
            user_id=user.id,
            chat_thread_id=thread.id,
            user_message="smuggle",
            history_text="[]",
            plan_provider=make_plan_provider(
                {"tool": "search_candidates", "arguments": {"query": ["a", "b"]}}
            ),
            compose_provider_factory=make_compose_factory(),
        )
    db_session.commit()

    run = only_one(db_session, WorkflowRun)
    assert run.status == "failed"
    assert only_one(db_session, AITrace).status == "validation_failed"


def test_plan_provider_failure_aborts_turn(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()
    captured: list = []

    with pytest.raises(ProviderTimeoutError):
        workflow.run(
            db_session,
            organization_id=organization.id,
            user_id=user.id,
            chat_thread_id=thread.id,
            user_message="pipeline",
            history_text="[]",
            plan_provider=make_plan_provider(failure=ProviderTimeoutError("timed out")),
            compose_provider_factory=make_compose_factory(capture=captured),
        )
    db_session.commit()

    assert captured == []
    run = only_one(db_session, WorkflowRun)
    step = only_one(db_session, WorkflowStepTrace)
    trace = only_one(db_session, AITrace)
    assert run.status == "failed"
    assert step.status == "failed"
    assert step.error_type == "ProviderTimeoutError"
    assert trace.status == "failed"


def test_compose_provider_failure_marks_compose_failed(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()

    with pytest.raises(ProviderTimeoutError):
        workflow.run(
            db_session,
            organization_id=organization.id,
            user_id=user.id,
            chat_thread_id=thread.id,
            user_message="pipeline",
            history_text="[]",
            plan_provider=make_plan_provider(
                {"tool": "summarize_pipeline", "arguments": {"status": "advanced"}}
            ),
            compose_provider_factory=make_compose_factory(
                failure=ProviderTimeoutError("timed out")
            ),
        )
    db_session.commit()

    run = only_one(db_session, WorkflowRun)
    steps = {
        step.step_name: step
        for step in db_session.scalars(
            select(WorkflowStepTrace).where(WorkflowStepTrace.workflow_run_id == run.id)
        )
    }
    plan_step = steps["plan_and_execute_tools"]
    compose_step = steps["compose_reply"]
    assert run.status == "failed"
    assert plan_step.status == "completed"
    assert compose_step.status == "failed"
    assert compose_step.error_type == "ProviderTimeoutError"


def test_reply_citing_missing_index_rejected(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()

    def bad_factory(invocations):
        return FakeAIProvider(
            provider="fake",
            model="fake-hera-composer",
            structured_payload=reply_payload("cited missing result", [7]),
        )

    with pytest.raises(ValidationError, match="outside the executed tool results"):
        workflow.run(
            db_session,
            organization_id=organization.id,
            user_id=user.id,
            chat_thread_id=thread.id,
            user_message="pipeline",
            history_text="[]",
            plan_provider=make_plan_provider(
                {"tool": "summarize_pipeline", "arguments": {"status": "advanced"}}
            ),
            compose_provider_factory=bad_factory,
        )
    db_session.commit()

    run = only_one(db_session, WorkflowRun)
    assert run.status == "failed"
    assert count_rows(db_session, AITrace) == 2


def test_invalid_plan_contract_rejected(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()

    bad_plan = FakeAIProvider(
        provider="fake",
        model="fake-hera-planner",
        structured_payload={"schema_version": AI_CONTRACT_SCHEMA_VERSION, "tool_calls": "nope"},
    )

    with pytest.raises(ValidationError, match="Invalid AI output contract"):
        workflow.run(
            db_session,
            organization_id=organization.id,
            user_id=user.id,
            chat_thread_id=thread.id,
            user_message="pipeline",
            history_text="[]",
            plan_provider=bad_plan,
            compose_provider_factory=make_compose_factory(),
        )
    db_session.commit()
    assert only_one(db_session, AITrace).status == "validation_failed"


def test_cross_organization_thread_fails_before_run(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    other_organization = Organization(name="Other Org")
    db_session.add(other_organization)
    db_session.flush()
    workflow = HERAAssistantWorkflow()

    with pytest.raises(ValidationError, match="different organization"):
        workflow.run(
            db_session,
            organization_id=other_organization.id,
            user_id=user.id,
            chat_thread_id=thread.id,
            user_message="pipeline",
            history_text="[]",
            plan_provider=make_plan_provider(),
            compose_provider_factory=make_compose_factory(),
        )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0
    assert count_rows(db_session, AITrace) == 0


def test_missing_thread_fails_before_run(db_session: Session) -> None:
    organization, user, _thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()

    with pytest.raises(NotFoundError, match="Workflow related entity was not found"):
        workflow.run(
            db_session,
            organization_id=organization.id,
            user_id=user.id,
            chat_thread_id=uuid.uuid4(),
            user_message="pipeline",
            history_text="[]",
            plan_provider=make_plan_provider(),
            compose_provider_factory=make_compose_factory(),
        )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0


def test_workflow_never_creates_chat_messages(db_session: Session) -> None:
    organization, user, thread = create_org_user_thread(db_session)
    workflow = HERAAssistantWorkflow()

    workflow.run(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
        chat_thread_id=thread.id,
        user_message="pipeline",
        history_text="[]",
        plan_provider=make_plan_provider(
            {"tool": "summarize_pipeline", "arguments": {"status": "advanced"}}
        ),
        compose_provider_factory=make_compose_factory(),
    )
    db_session.commit()

    from app.models import ChatMessage

    assert count_rows(db_session, ChatMessage) == 0


def only_one(db_session: Session, model):
    return db_session.scalar(select(model).limit(1))


# --------------------------------------------------------------------------- #
# SoalProvider (real provider, optional)
# --------------------------------------------------------------------------- #


def _make_soal_providers() -> tuple[object, object]:
    api_key = os.environ.get("SOAL_API_KEY")
    if not api_key:
        pytest.skip("SOAL_API_KEY is not set; skipping real Soal provider tests.")
    settings = Settings(
        ai_provider="soal",
        soal_api_key=api_key,
        soal_model="gemini-3.5-flash",
    )
    return get_provider(settings), get_provider(settings)


@pytest.mark.soal
class TestSoalProviderHERAAssistant:
    def test_live_run_completes_turn(self, db_session: Session) -> None:
        organization, user, thread = create_org_user_thread(db_session)
        plan_provider, compose_provider = _make_soal_providers()
        workflow = HERAAssistantWorkflow()

        result = workflow.run(
            db_session,
            organization_id=organization.id,
            user_id=user.id,
            chat_thread_id=thread.id,
            user_message="How many applications are in the pipeline?",
            history_text="[]",
            plan_provider=plan_provider,
            compose_provider_factory=lambda _invocations: compose_provider,
        )
        db_session.commit()

        run = db_session.get(WorkflowRun, result.workflow_run_id)
        plan_trace = db_session.get(AITrace, result.plan_ai_trace_id)
        compose_trace = db_session.get(AITrace, result.compose_ai_trace_id)
        assert run.status == "completed"
        assert plan_trace.provider == "soal"
        assert compose_trace.provider == "soal"
        assert result.reply.answer.strip()
        assert result.invocations[0].tool == "summarize_pipeline"
