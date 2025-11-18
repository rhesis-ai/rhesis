"""
Base tool interface for Penelope.

Tools are Penelope's primary way of interacting with the world and gathering information.
Following Anthropic's recommendations, each tool should be extensively documented
with clear examples and edge case handling.

Note: Tool parameter validation is handled via Pydantic schemas (SendMessageParams,
AnalyzeResponseParams, ExtractInformationParams) which are part of the ToolCall
structured output schema.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Result from a tool execution."""

    success: bool = Field(description="Whether the tool execution succeeded")
    output: Dict[str, Any] = Field(description="Output data from the tool")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the execution"
    )


class Tool(ABC):
    """
    Base class for all Penelope tools.

    Following Anthropic's Agent-Computer Interface (ACI) principles:
    1. Clear documentation (like writing for a junior developer)
    2. Example usage included
    3. Edge cases documented
    4. No formatting overhead
    5. Parameters that make sense to the model
    """

    def is_target_interaction_tool(self) -> bool:
        """
        Determine if this tool represents a target interaction (counts as a turn).

        Target interaction tools are those that communicate with the system under test.
        Internal tools (analysis, extraction, etc.) do not count as turns.

        Returns:
            True if this tool interacts with the target, False for internal tools
        """
        # Use the ToolType enum for reliable classification
        from rhesis.penelope.context import ToolType
        return ToolType.is_target_interaction(self.name)

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Detailed description of what the tool does.

        Should include:
        - Purpose and capabilities
        - When to use it
        - When NOT to use it
        - Best practices
        - Common pitfalls to avoid
        """
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the tool with the given parameters.

        Parameters are validated via Pydantic schemas before reaching this method,
        so tools can assume valid input.

        Args:
            **kwargs: Tool parameters (already validated via Pydantic)

        Returns:
            ToolResult with execution outcome
        """
        pass
