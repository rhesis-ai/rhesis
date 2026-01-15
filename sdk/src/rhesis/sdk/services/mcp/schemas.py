"""Pydantic schemas for MCP Agent structured outputs."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ToolCall(BaseModel):
    """Represents a single tool invocation."""

    model_config = {"extra": "forbid"}

    tool_name: str = Field(description="Name of the MCP tool to call")
    arguments: str = Field(
        default="{}",
        description="Arguments for the tool as a JSON string or dict. "
        'Example: \'{"page_id": "123", "query": "search term"}\' or {"page_id": "123"}',
    )

    @field_validator("arguments", mode="after")
    @classmethod
    def parse_arguments_to_dict(cls, v):
        """Parse JSON string to dictionary for internal use."""
        import json

        try:
            return json.loads(v) if isinstance(v, str) else v
        except json.JSONDecodeError:
            # If it's not valid JSON, return empty dict
            return {}


class AgentAction(BaseModel):
    """LLM's structured response in the ReAct loop."""

    reasoning: str = Field(description="Your step-by-step reasoning about what to do next")
    action: Literal["call_tool", "finish"] = Field(
        description="Action to take: 'call_tool' to execute tools, 'finish' to return final answer"
    )
    tool_calls: List[ToolCall] = Field(
        default_factory=list,
        description="List of tools to call if action='call_tool'. Can be multiple tools.",
    )
    final_answer: Optional[str] = Field(
        default=None,
        description="Your final answer if action='finish'. Required when action='finish'.",
    )


class ToolResult(BaseModel):
    """Result from executing an MCP tool.

    A ToolResult is returned when the MCP server successfully received and
    processed the tool call. The 'success' field indicates whether the
    tool's OPERATION succeeded at the application layer.

    If the tool cannot be executed at all (connection failures, timeouts,
    configuration errors), the executor raises an exception instead.

    The agent receives ALL ToolResults (success or failure) and passes them
    to the LLM, which reasons about failures and decides how to respond.

    Examples:
        - Connection timeout → MCPConnectionError raised (no ToolResult)
        - Tool config missing → MCPConfigurationError raised (no ToolResult)
        - Tool executed, found resource → ToolResult(success=True, content="...")
        - Tool executed, resource not found → ToolResult(success=False, error="Not found")
        - Tool executed, 401 auth error → ToolResult(success=False, error="Unauthorized")
        - Tool executed, missing parameter → ToolResult(success=False, error="Missing 'id'")
    """

    tool_name: str = Field(description="Name of the tool that was executed")
    success: bool = Field(
        description="Whether the tool's operation succeeded at the application layer. "
        "True = operation succeeded. "
        "False = tool executed but operation failed for ANY reason "
        "(validation, not found, auth, rate limit, etc.)."
    )
    content: str = Field(default="", description="Content returned by the tool when success=True")
    error: Optional[str] = Field(
        default=None,
        description="Error message when success=False. "
        "The LLM will reason about this error and decide how to respond.",
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
        default_factory=list, description="Results from tool executions"
    )


class AgentResult(BaseModel):
    """Final result from the agent's execution."""

    final_answer: str = Field(description="The agent's final answer to the query")
    execution_history: List[ExecutionStep] = Field(
        default_factory=list, description="Full history of execution steps"
    )
    iterations_used: int = Field(description="Number of iterations executed")
    max_iterations_reached: bool = Field(
        description="Whether the agent stopped due to hitting max iterations"
    )
    success: bool = Field(default=True, description="Whether the agent completed successfully")
    error: Optional[str] = Field(
        default=None, description="Error message produced by the agent code, if execution failed"
    )
