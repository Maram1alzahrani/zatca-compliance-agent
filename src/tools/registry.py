from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable


class ToolCallStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class UnknownToolError(KeyError):
    pass


@dataclass(frozen=True, slots=True)
class ToolCallEvent:
    sequence: int
    tool_name: str
    status: ToolCallStatus
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    handler: Callable[..., Any]
    summarize_input: Callable[[dict[str, Any]], dict[str, Any]]
    summarize_output: Callable[[Any], dict[str, Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(self._definitions)

    def register(self, definition: ToolDefinition) -> None:
        if not definition.name or definition.name in self._definitions:
            raise ValueError(f"Invalid or duplicate tool name: {definition.name!r}")
        self._definitions[definition.name] = definition

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        trace: list[ToolCallEvent],
    ) -> Any:
        definition = self._definitions.get(tool_name)
        if definition is None:
            trace.append(ToolCallEvent(len(trace) + 1, tool_name, ToolCallStatus.FAILED, {}, {}, "UnknownToolError"))
            raise UnknownToolError(tool_name)
        input_summary = definition.summarize_input(arguments)
        try:
            output = definition.handler(**arguments)
        except Exception as exc:
            trace.append(
                ToolCallEvent(
                    len(trace) + 1,
                    tool_name,
                    ToolCallStatus.FAILED,
                    input_summary,
                    {},
                    type(exc).__name__,
                )
            )
            raise
        trace.append(
            ToolCallEvent(
                len(trace) + 1,
                tool_name,
                ToolCallStatus.SUCCESS,
                input_summary,
                definition.summarize_output(output),
            )
        )
        return output
