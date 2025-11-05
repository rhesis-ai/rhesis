"""Pydantic schemas for MCP Agent structured outputs."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a single tool invocation."""

    tool_name: str = Field(description="Name of the MCP tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")


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
    """Result from executing a tool."""

    tool_name: str = Field(description="Name of the tool that was executed")
    success: bool = Field(description="Whether the tool execution succeeded")
    content: str = Field(default="", description="Content returned by the tool")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")


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
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
