"""Structured AI output contracts for the HERA assistant chat agent.

Phase Chat. The assistant is an LLM agent that plans tool calls against an
authorized tool registry, executes those tools through real domain services,
and composes a grounded reply. Two structured contracts bound the two LLM
steps:

- ``HERAPlanOutput``: the plan step decides whether (and which) authorized
  read-only tools to invoke. It carries only scalar arguments; the tool-name
  and argument authorization happens later against the tool registry, so the
  LLM can never run anything outside the authorized tool set.
- ``HERAReplyOutput``: the compose step writes the final answer and optional
  in-app links, grounded in the executed tool results.

Nothing here persists, touches a database, or implies a decision. The
assistant is read-only: no tool in the registry can change state.
"""

from typing import Annotated, Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from app.ai.contracts.schema import AI_CONTRACT_SCHEMA_VERSION, SchemaVersion
from app.services.errors import ValidationError

MAX_TOOL_CALLS = 5
MAX_REPLY_LINKS = 3

ScalarValue = str | int | float | bool | None

T = TypeVar("T", bound=BaseModel)


def _validate_contract(contract_type: type[T], data: Any) -> T:
    try:
        return contract_type.model_validate(data)
    except PydanticValidationError as error:
        raise ValidationError(f"Invalid AI output contract: {error}") from error


class HERAToolCall(BaseModel):
    """One authorized-tool invocation the plan step selected."""

    model_config = ConfigDict(extra="forbid")

    tool: Annotated[str, Field(min_length=1, max_length=64)]
    arguments: dict[str, ScalarValue] = Field(default_factory=dict)
    reason: Annotated[str | None, Field(max_length=200)] = None


class HERAPlanOutput(BaseModel):
    """Structured plan: which authorized tools to run (schema v1.1)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = AI_CONTRACT_SCHEMA_VERSION
    tool_calls: list[HERAToolCall] = Field(default_factory=list, max_length=MAX_TOOL_CALLS)


class HERALink(BaseModel):
    """An in-app navigation link the assistant may offer in its reply."""

    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, Field(min_length=1, max_length=60)]
    path: Annotated[str, Field(min_length=1, max_length=200)]


class HERAReplyOutput(BaseModel):
    """Structured assistant reply grounded in executed tool results."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = AI_CONTRACT_SCHEMA_VERSION
    answer: Annotated[str, Field(min_length=1, max_length=4000)]
    used_tool_indices: list[int] = Field(default_factory=list, max_length=MAX_TOOL_CALLS)
    links: list[HERALink] = Field(default_factory=list, max_length=MAX_REPLY_LINKS)


def validate_hera_plan(data: Any) -> HERAPlanOutput:
    """Validate raw plan data into a HERAPlanOutput.

    Structural validation only (shape, scalar arguments, counts). Tool-name and
    argument authorization is delegated to the authorized-tool registry so the
    LLM can never invoke anything outside it.
    """
    return _validate_contract(HERAPlanOutput, data)


def validate_hera_reply(data: Any, *, tool_result_count: int = 0) -> HERAReplyOutput:
    """Validate raw reply data into a HERAReplyOutput.

    In addition to shape validation, every ``used_tool_indices`` entry must be
    a valid index into the executed tool results, so the assistant can only
    cite results that actually ran. Links must be in-app absolute paths.
    """
    reply = _validate_contract(HERAReplyOutput, data)
    for index in reply.used_tool_indices:
        if index < 0 or index >= tool_result_count:
            raise ValidationError(
                f"Assistant reply cited tool result index {index} outside the "
                f"executed tool results (count {tool_result_count})."
            )
    for link in reply.links:
        if not link.path.startswith("/") or link.path.startswith("//"):
            raise ValidationError("Assistant reply links must be in-app absolute paths.")
    return reply
