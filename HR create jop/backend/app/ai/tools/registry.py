"""Authorized-tool registry assembly for the HERA assistant.

Builds the lookup table and planner-facing description from the read-only
``PIPELINE_TOOLS`` catalog and exposes the authorization gate
(``validate_and_coerce_arguments``), which the assistant workflow applies to
every planned tool invocation before any handler runs. Tools not present in
``TOOL_REGISTRY`` are unauthorized: the workflow reports the failed invocation
and never executes it.
"""

from __future__ import annotations

import json

from app.ai.tools.pipeline_tools import PIPELINE_TOOLS, RegisteredTool
from app.services.errors import ValidationError

TOOL_CATALOG: list[RegisteredTool] = list(PIPELINE_TOOLS)
TOOL_REGISTRY: dict[str, RegisteredTool] = {tool.name: tool for tool in TOOL_CATALOG}
TOOLS_DESCRIPTION = json.dumps(
    [
        {
            "name": tool.name,
            "description": tool.description,
            "arguments": tool.arguments_schema,
        }
        for tool in TOOL_CATALOG
    ],
    sort_keys=True,
    ensure_ascii=False,
)


def get_tool(name: str) -> RegisteredTool | None:
    """Return the registered tool for a name, or ``None`` when unauthorized."""
    return TOOL_REGISTRY.get(name)


def validate_and_coerce_arguments(tool: RegisteredTool, arguments: object) -> dict[str, object]:
    """Authorize and coerce plan arguments before any handler runs.

    Rejects unknown keys, non-scalar values, and missing required arguments and
    coerces strings to integers/booleans where the argument spec declares them,
    so a language-model plan can never smuggle unsupported input into a handler.
    """
    if not isinstance(arguments, dict):
        raise ValidationError(f"Arguments for tool {tool.name!r} must be an object.")
    properties = tool.arguments_schema.get("properties", {})
    required = tool.arguments_schema.get("required", [])
    unknown = sorted(set(arguments) - set(properties))
    if unknown:
        raise ValidationError(f"Unknown argument(s) for tool {tool.name!r}: {', '.join(unknown)}.")
    missing = [name for name in required if name not in arguments]
    if missing:
        raise ValidationError(
            f"Missing required argument(s) for tool {tool.name!r}: {', '.join(missing)}."
        )
    coerced: dict[str, object] = {}
    for name, value in arguments.items():
        spec_type = properties.get(name, {}).get("type", "string")
        if isinstance(value, (list, dict)):
            raise ValidationError(
                f"Argument {name!r} for tool {tool.name!r} must be a scalar value."
            )
        if spec_type == "integer":
            if isinstance(value, bool) or not str(value).lstrip("-").isdigit():
                raise ValidationError(
                    f"Argument {name!r} for tool {tool.name!r} must be an integer."
                )
            coerced[name] = int(value)
        elif spec_type == "boolean":
            if isinstance(value, bool):
                coerced[name] = value
            elif isinstance(value, str) and value.lower() in {"true", "false"}:
                coerced[name] = value.lower() == "true"
            else:
                raise ValidationError(
                    f"Argument {name!r} for tool {tool.name!r} must be a boolean."
                )
        else:
            coerced[name] = None if value is None else str(value)
    return coerced


__all__ = [
    "PIPELINE_TOOLS",
    "RegisteredTool",
    "TOOL_CATALOG",
    "TOOL_REGISTRY",
    "TOOLS_DESCRIPTION",
    "get_tool",
    "validate_and_coerce_arguments",
]
