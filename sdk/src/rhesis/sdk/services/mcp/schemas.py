"""Pydantic schemas for MCP Agent structured outputs."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a single tool invocation."""

    model_config = {"extra": "forbid"}

    tool_name: str = Field(description="Name of the MCP tool to call")
    arguments: Any = Field(default={}, description="Arguments for the tool as a JSON object")


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


# Search and Extract Agent Schemas


class PageMetadata(BaseModel):
    """Unified page metadata across all MCP servers."""

    page_id: str = Field(description="Unique identifier from the service")
    title: Optional[str] = Field(default=None, description="Page/file/document title")
    url: Optional[str] = Field(default=None, description="URL to access the page")
    last_edited: Optional[str] = Field(default=None, description="Last edit timestamp (ISO format)")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp (ISO format)")
    excerpt: Optional[str] = Field(default=None, description="Brief preview/summary of content")
    author: Optional[str] = Field(default=None, description="Author/creator")
    source_type: str = Field(description="Source type: 'notion', 'github', 'slack', etc.")
    raw_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Original service-specific metadata"
    )


class SearchResult(BaseModel):
    """Result from MCPSearchAgent."""

    pages: List[PageMetadata] = Field(description="List of pages found")
    total_found: int = Field(description="Total number of pages found")
    query: str = Field(description="Original search query")
    execution_history: List[ExecutionStep] = Field(default_factory=list)
    iterations_used: int = Field(default=0)
    success: bool = Field(default=True)
    error: Optional[str] = Field(default=None)


class ExtractedPage(BaseModel):
    """Content extracted from a single page."""

    page_id: str = Field(description="Unique identifier")
    title: Optional[str] = Field(default=None, description="Page title")
    content: str = Field(description="Full extracted content as markdown/text")
    metadata: PageMetadata = Field(description="Page metadata")
    source_type: str = Field(description="Source type: 'notion', 'github', etc.")


class ExtractionResult(BaseModel):
    """Result from MCPExtractAgent."""

    pages: List[ExtractedPage] = Field(description="Extracted pages with content")
    total_extracted: int = Field(description="Number of successfully extracted pages")
    execution_history: List[ExecutionStep] = Field(default_factory=list)
    iterations_used: int = Field(default=0)
    success: bool = Field(default=True)
    error: Optional[str] = Field(default=None)
