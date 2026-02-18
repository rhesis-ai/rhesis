"""Shared schemas for agent structured outputs."""

import json
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, BeforeValidator, Field, WithJsonSchema


def _parse_arguments(v: Any) -> Dict[str, Any]:
    """Coerce JSON strings and other values to ``dict``."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return {}
    return v if isinstance(v, dict) else {}


# Runtime type is Dict[str, Any].
# JSON schema presented to the LLM is {"type": "string"} so the model
# produces a JSON-encoded string (e.g. '{"goal": "..."}') which the
# BeforeValidator transparently parses into a dict.
ToolArguments = Annotated[
    Dict[str, Any],
    BeforeValidator(_parse_arguments),
    WithJsonSchema(
        {
            "type": "string",
            "default": "{}",
            "description": (
                "Arguments for the tool as a JSON string. "
                'Example: \'{"page_id": "123", "query": "term"}\''
            ),
        }
    ),
]


class ToolCall(BaseModel):
    """Represents a single tool invocation."""

    model_config = {"extra": "forbid"}

    tool_name: str = Field(description="Name of the tool to call")
    arguments: ToolArguments = Field(default_factory=dict)


class AgentAction(BaseModel):
    """LLM's structured response in the ReAct loop."""

    reasoning: str = Field(description="Your step-by-step reasoning about what to do next")
    action: Literal["call_tool", "finish"] = Field(
        description=(
            "Action to take: 'call_tool' to execute tools, 'finish' to return final answer"
        )
    )
    tool_calls: List[ToolCall] = Field(
        default_factory=list,
        description=("List of tools to call if action='call_tool'. Can be multiple tools."),
    )
    final_answer: Optional[str] = Field(
        default=None,
        description=("Your final answer if action='finish'. Required when action='finish'."),
    )


class ToolResult(BaseModel):
    """Result from executing a tool.

    A ToolResult is returned when the tool was successfully invoked.
    The 'success' field indicates whether the tool's OPERATION succeeded
    at the application layer.

    If the tool cannot be executed at all (connection failures, timeouts,
    configuration errors), the executor raises an exception instead.
    """

    tool_name: str = Field(description="Name of the tool that was executed")
    success: bool = Field(
        description=(
            "Whether the tool's operation succeeded. "
            "True = operation succeeded. "
            "False = tool executed but operation failed."
        )
    )
    content: str = Field(
        default="",
        description="Content returned by the tool when success=True",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message when success=False.",
    )


class ExecutionStep(BaseModel):
    """Single iteration in the ReAct loop."""

    iteration: int = Field(description="Iteration number (1-indexed)")
    reasoning: str = Field(description="Agent's reasoning for this step")
    action: str = Field(description="Action taken: 'call_tool' or 'finish'")
    tool_calls: List[ToolCall] = Field(
        default_factory=list, description="Tools called in this step"
    )
    tool_results: List[ToolResult] = Field(
        default_factory=list,
        description="Results from tool executions",
    )


class AgentResult(BaseModel):
    """Final result from the agent's execution."""

    final_answer: str = Field(description="The agent's final answer to the query")
    execution_history: List[ExecutionStep] = Field(
        default_factory=list,
        description="Full history of execution steps",
    )
    iterations_used: int = Field(description="Number of iterations executed")
    max_iterations_reached: bool = Field(
        description=("Whether the agent stopped due to hitting max iterations")
    )
    success: bool = Field(
        default=True,
        description="Whether the agent completed successfully",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed",
    )
