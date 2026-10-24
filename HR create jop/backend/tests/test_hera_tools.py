"""Tests for the HERA authorized-tool registry and argument authorization gate."""

from __future__ import annotations

import pytest

from app.ai.tools import (
    PIPELINE_TOOLS,
    TOOL_CATALOG,
    TOOL_REGISTRY,
    TOOLS_DESCRIPTION,
    get_tool,
    validate_and_coerce_arguments,
)
from app.services.errors import ValidationError


def test_all_pipeline_tools_registered_exactly_once() -> None:
    assert len(TOOL_CATALOG) == 8
    assert len(TOOL_REGISTRY) == 8
    assert len({tool.name for tool in TOOL_CATALOG}) == len(TOOL_CATALOG)


def test_expected_tool_names_present() -> None:
    expected = {
        "summarize_pipeline",
        "list_jobs",
        "search_candidates",
        "get_talent_pool",
        "list_interviews",
        "get_application_details",
        "get_interview_slots",
        "get_ai_activity",
    }
    assert expected == set(TOOL_REGISTRY)


def test_unknown_tool_returns_none() -> None:
    assert get_tool("drop_database") is None


def test_tools_description_is_valid_json_and_mentions_arguments() -> None:
    import json

    parsed = json.loads(TOOLS_DESCRIPTION)
    assert isinstance(parsed, list)
    assert all("name" in item and "description" in item and "arguments" in item for item in parsed)


def test_arbitrary_json_serializable_arguments() -> None:
    """Handler payloads keep the JSON round-trip friendly for chat responses."""
    import json

    for tool in TOOL_CATALOG:
        for _, spec in tool.arguments_schema["properties"].items():
            json.dumps(spec)


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        ("summarize_pipeline", {"status": "advanced"}, {"status": "advanced"}),
        ("summarize_pipeline", {"status": "hold", "limit": "5"}, {"status": "hold", "limit": 5}),
        ("search_candidates", {"query": "Sara"}, {"query": "Sara"}),
        ("get_interview_slots", {"scheduled_date": "2026-09-10"}, {"scheduled_date": "2026-09-10"}),
        ("get_application_details", {"application_id": "abc"}, {"application_id": "abc"}),
        ("list_jobs", {"status": "active"}, {"status": "active"}),
        ("get_talent_pool", {"limit": 3}, {"limit": 3}),
        ("get_ai_activity", {}, {}),
    ],
)
def test_valid_arguments_coerced(name, arguments, expected) -> None:
    tool = get_tool(name)
    assert tool is not None
    assert validate_and_coerce_arguments(tool, arguments) == expected


def test_integer_string_coerced_within_bounds_later() -> None:
    tool = get_tool("list_jobs")
    assert tool is not None
    result = validate_and_coerce_arguments(tool, {"limit": "999"})
    assert result == {"limit": 999}


def test_unknown_argument_rejected() -> None:
    tool = get_tool("summarize_pipeline")
    assert tool is not None
    with pytest.raises(ValidationError, match="Unknown argument"):
        validate_and_coerce_arguments(tool, {"status": "advanced", "exec": "rm -rf"})


def test_non_scalar_argument_rejected() -> None:
    tool = get_tool("summarize_pipeline")
    assert tool is not None
    with pytest.raises(ValidationError, match="scalar"):
        validate_and_coerce_arguments(tool, {"limit": [1, 2, 3]})


def test_non_dict_arguments_rejected() -> None:
    tool = get_tool("summarize_pipeline")
    assert tool is not None
    with pytest.raises(ValidationError, match="must be an object"):
        validate_and_coerce_arguments(tool, "advanced")


def test_boolean_coercion_from_string() -> None:
    from app.ai.tools import RegisteredTool

    tool = RegisteredTool(
        name="fake_boolean_tool",
        description="for testing",
        arguments_schema={
            "properties": {"include_rejected": {"type": "boolean"}},
            "required": [],
        },
        handler=lambda **_: {},
    )
    assert validate_and_coerce_arguments(tool, {"include_rejected": "true"}) == {
        "include_rejected": True
    }
    assert validate_and_coerce_arguments(tool, {"include_rejected": True}) == {
        "include_rejected": True
    }
    with pytest.raises(ValidationError, match="must be a boolean"):
        validate_and_coerce_arguments(tool, {"include_rejected": "maybe"})


def test_missing_required_argument_rejected() -> None:
    tool = get_tool("search_candidates")
    assert tool is not None
    from app.ai.tools import RegisteredTool

    # Simulate a spec that marks query required without mutating the shared catalog.
    strict = RegisteredTool(
        name=tool.name,
        description=tool.description,
        arguments_schema={
            "properties": tool.arguments_schema["properties"],
            "required": ["query"],
        },
        handler=tool.handler,
    )
    with pytest.raises(ValidationError, match="Missing required"):
        validate_and_coerce_arguments(strict, {})


def test_handlers_accept_identity_context() -> None:
    """Every handler exposes the org-scoped identity parameters."""
    import inspect

    for tool in PIPELINE_TOOLS:
        parameters = inspect.signature(tool.handler).parameters
        assert "organization_id" in parameters
        assert "user_id" in parameters
        assert "db" in parameters
