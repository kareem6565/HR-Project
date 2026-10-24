"""HERA assistant agent workflow (Phase Chat).

Orchestrates a single deterministic conversational turn for a chat thread:

1. ``plan_and_execute_tools`` — the plan step asks the AI provider for a
   structured plan (which authorized tools to call, with scalar arguments),
   validates the plan contract, executes every planned tool against the
   authorized-tool registry (read-only, org-scoped domain services), and
   isolates each invocation so a failing/boundary-coopting tool can never abort
   the exchange.
2. ``compose_reply`` — the compose step asks the AI provider for a structured
   reply grounded in the executed tool results, validates the reply contract
   (including that cited result indices actually exist), and returns it.

This workflow never persists chat messages and never commits; the caller owns
the transaction. It produces a read-only answer only — no decision, no state
change, no direct database access from the LLM: the authorized-tool registry is
the only path out of the prompt.

The compose provider is resolved *after* plan-and-tool execution through a
factory so the caller can ground deterministic fake-mode payloads in the real
tool results before the second LLM step runs (mirroring how evaluation routes
derive deterministic evidence/explanation payloads from real data).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.ai.contracts import (
    AI_CONTRACT_SCHEMA_VERSION,
    HERAPlanOutput,
    HERAReplyOutput,
    validate_hera_plan,
    validate_hera_reply,
)
from app.ai.providers.base import AIProvider, StructuredGenerationRequest
from app.ai.providers.errors import ProviderError
from app.ai.tools import TOOL_REGISTRY, RegisteredTool, validate_and_coerce_arguments
from app.services.errors import ApplicationError, ValidationError
from app.services.workflow_trace_service import WorkflowTraceService

WORKFLOW_TYPE = "hera_assistant"
STEP_PLAN = "plan_and_execute_tools"
STEP_COMPOSE = "compose_reply"
PLAN_AI_COMPONENT = "hera_planner"
COMPOSE_AI_COMPONENT = "hera_reply_composer"
PROMPT_VERSION = "1"

MAX_COMPOSE_INPUT_CHARS = 25000


def _sha256(value: str) -> str:
    """Return the hex SHA-256 digest of a string value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _serialize(value: object) -> str:
    """Serialize a value deterministically for hashing or provider input."""
    return json.dumps(value, sort_keys=True, default=str)


def _trim(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


@dataclass(frozen=True)
class HERAToolInvocation:
    """The executed outcome of one planned tool invocation."""

    tool: str
    arguments: dict[str, Any]
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@dataclass(frozen=True)
class HERAAssistantResult:
    """Outcome of a successful HERA assistant conversational turn."""

    plan: HERAPlanOutput
    invocations: list[HERAToolInvocation]
    reply: HERAReplyOutput
    workflow_run_id: uuid.UUID
    plan_step_id: uuid.UUID
    compose_step_id: uuid.UUID
    plan_ai_trace_id: uuid.UUID
    compose_ai_trace_id: uuid.UUID


class HERAAssistantWorkflow:
    """Orchestrate a single HERA assistant turn (plan -> tools -> compose)."""

    def __init__(
        self,
        *,
        tools: Mapping[str, RegisteredTool] | None = None,
        trace_service: WorkflowTraceService | None = None,
    ) -> None:
        self._tools = tools if tools is not None else TOOL_REGISTRY
        self._catalog_text = json.dumps(
            [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "arguments": tool.arguments_schema,
                }
                for tool in self._tools.values()
            ],
            sort_keys=True,
            ensure_ascii=False,
        )
        self._trace_service = trace_service or WorkflowTraceService()

    def run(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        chat_thread_id: uuid.UUID,
        user_message: str,
        history_text: str,
        plan_provider: AIProvider,
        compose_provider_factory,
    ) -> HERAAssistantResult:
        """Execute one conversational turn, raising on any hard failure."""
        run = self._trace_service.start_run(
            db,
            organization_id=organization_id,
            workflow_type=WORKFLOW_TYPE,
            related_entity_type="chat_thread",
            related_entity_id=chat_thread_id,
            status="running",
        )
        plan_step = self._trace_service.start_step(
            db,
            workflow_run_id=run.id,
            step_name=STEP_PLAN,
            status="running",
        )
        input_reference = self._input_reference(chat_thread_id, user_message)
        plan, _plan_result, plan_trace = self._run_ai_component(
            db,
            step=plan_step,
            run=run,
            provider=plan_provider,
            component_name=PLAN_AI_COMPONENT,
            input_text=self._plan_input(user_message, history_text),
            output_schema=HERAPlanOutput,
            validate_fn=validate_hera_plan,
            input_reference=input_reference,
        )
        invocations = [
            self._execute_tool(
                db,
                call,
                organization_id=organization_id,
                user_id=user_id,
            )
            for call in plan.tool_calls
        ]
        self._trace_service.mark_step_completed(db, workflow_step_trace_id=plan_step.id)

        compose_step = self._trace_service.start_step(
            db,
            workflow_run_id=run.id,
            step_name=STEP_COMPOSE,
            status="running",
        )
        compose_provider = compose_provider_factory(list(invocations))
        reply, _reply_result, compose_trace = self._run_ai_component(
            db,
            step=compose_step,
            run=run,
            provider=compose_provider,
            component_name=COMPOSE_AI_COMPONENT,
            input_text=self._compose_input(user_message, history_text, invocations),
            output_schema=HERAReplyOutput,
            validate_fn=validate_hera_reply,
            validate_kwargs={"tool_result_count": len(invocations)},
            input_reference=input_reference,
        )
        self._trace_service.mark_step_completed(db, workflow_step_trace_id=compose_step.id)
        self._trace_service.mark_run_completed(db, workflow_run_id=run.id)

        return HERAAssistantResult(
            plan=plan,
            invocations=invocations,
            reply=reply,
            workflow_run_id=run.id,
            plan_step_id=plan_step.id,
            compose_step_id=compose_step.id,
            plan_ai_trace_id=plan_trace.id,
            compose_ai_trace_id=compose_trace.id,
        )

    def _execute_tool(
        self,
        db: Session,
        call,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> HERAToolInvocation:
        """Authorize + run one planned tool, isolating any failure."""
        tool = self._tools.get(call.tool)
        if tool is None:
            return HERAToolInvocation(
                tool=call.tool,
                arguments=dict(call.arguments),
                ok=False,
                error=f"Tool {call.tool!r} is not an authorized tool.",
            )
        try:
            coerced = validate_and_coerce_arguments(tool, call.arguments)
        except ApplicationError as error:
            return HERAToolInvocation(
                tool=call.tool,
                arguments=dict(call.arguments),
                ok=False,
                error=_trim(str(error), 300),
            )
        try:
            data = tool.handler(
                db,
                organization_id=organization_id,
                user_id=user_id,
                **coerced,
            )
        except ApplicationError as error:
            return HERAToolInvocation(
                tool=call.tool,
                arguments=coerced,
                ok=False,
                error=_trim(str(error), 300),
            )
        except Exception as error:  # pragma: no cover - tool isolation boundary
            return HERAToolInvocation(
                tool=call.tool,
                arguments=coerced,
                ok=False,
                error=_trim(f"Unexpected tool error: {error}", 300),
            )
        return HERAToolInvocation(
            tool=call.tool,
            arguments=coerced,
            ok=True,
            data=data,
            error=None,
        )

    def _run_ai_component(
        self,
        db: Session,
        *,
        step,
        run,
        provider: AIProvider,
        component_name: str,
        input_text: str,
        output_schema: type,
        validate_fn,
        validate_kwargs: dict | None = None,
        input_reference: dict[str, str],
    ):
        try:
            result = provider.generate_structured(
                StructuredGenerationRequest(
                    input=input_text,
                    output_schema=output_schema,
                    schema_version=AI_CONTRACT_SCHEMA_VERSION,
                    metadata={"workflow": WORKFLOW_TYPE, "component": component_name},
                )
            )
        except ProviderError as error:
            self._trace_service.record_ai_trace(
                db,
                workflow_step_trace_id=step.id,
                ai_component_name=component_name,
                status="failed",
                prompt_version=PROMPT_VERSION,
                input_schema_version=AI_CONTRACT_SCHEMA_VERSION,
                output_schema_version=AI_CONTRACT_SCHEMA_VERSION,
                input_reference=input_reference,
            )
            self._trace_service.mark_step_failed(
                db,
                workflow_step_trace_id=step.id,
                error_type=type(error).__name__,
                error_message=str(error),
            )
            self._trace_service.mark_run_failed(db, workflow_run_id=run.id)
            raise

        try:
            validated = validate_fn(result.data, **(validate_kwargs or {}))
        except ValidationError as error:
            self._trace_service.record_ai_trace(
                db,
                workflow_step_trace_id=step.id,
                ai_component_name=component_name,
                status="validation_failed",
                provider=result.provider,
                model_name=result.model,
                prompt_version=PROMPT_VERSION,
                input_schema_version=AI_CONTRACT_SCHEMA_VERSION,
                output_schema_version=result.schema_version,
                latency_ms=result.latency_ms,
                input_reference=input_reference,
                validation_error={"schema": result.schema_version, "message": str(error)},
            )
            self._trace_service.mark_step_failed(
                db,
                workflow_step_trace_id=step.id,
                error_type="ValidationError",
                error_message=str(error),
            )
            self._trace_service.mark_run_failed(db, workflow_run_id=run.id)
            raise

        ai_trace = self._trace_service.record_ai_trace(
            db,
            workflow_step_trace_id=step.id,
            ai_component_name=component_name,
            status="succeeded",
            provider=result.provider,
            model_name=result.model,
            prompt_version=PROMPT_VERSION,
            input_schema_version=AI_CONTRACT_SCHEMA_VERSION,
            output_schema_version=result.schema_version,
            latency_ms=result.latency_ms,
            input_reference=input_reference,
            output_reference={"output_sha256": _sha256(_serialize(validated.model_dump()))},
            token_usage=result.token_usage,
        )
        return validated, result, ai_trace

    @staticmethod
    def _input_reference(chat_thread_id: uuid.UUID, user_message: str) -> dict[str, str]:
        return {
            "entity": "chat_thread",
            "entity_id": str(chat_thread_id),
            "message_sha256": _sha256(_serialize(user_message)),
        }

    def _plan_input(self, user_message: str, history_text: str) -> str:
        return _serialize(
            {
                "system": (
                    "You are HERA, a read-only HR recruitment assistant. Reply plans by "
                    "choosing authorized tools. Only call a tool the data actually "
                    "requires; if the user is just chatting, return an empty tool_calls "
                    "list. Never invent entity ids: only use an application/id the user "
                    "provided. Arguments must be scalar. Prefer small limits."
                ),
                "authorized_tools": json.loads(self._catalog_text),
                "conversation_history": history_text,
                "user_message": user_message,
            }
        )

    def _compose_input(
        self,
        user_message: str,
        history_text: str,
        invocations: list[HERAToolInvocation],
    ) -> str:
        results = [
            {
                "index": index,
                "tool": invocation.tool,
                "ok": invocation.ok,
                "data": invocation.data if invocation.ok else None,
                "error": invocation.error if not invocation.ok else None,
            }
            for index, invocation in enumerate(invocations)
        ]
        rendered = _serialize(
            {
                "system": (
                    "You are HERA, a read-only HR recruitment assistant. Answer in the "
                    "same language as the user's message, using ONLY the tool results "
                    "above. Never invent numbers or entities. Be concise. You may offer "
                    "at most 3 in-app absolute links. If every tool failed, explain "
                    "plainly and suggest what the user can do."
                ),
                "conversation_history": history_text,
                "user_message": user_message,
                "tool_results": results,
            }
        )
        if len(rendered) > MAX_COMPOSE_INPUT_CHARS:
            rendered = rendered[:MAX_COMPOSE_INPUT_CHARS] + "...[truncated]"
        return rendered
