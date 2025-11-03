"""
Target interaction tool for Penelope.

This is Penelope's primary tool for communicating with the system under test.
Following Anthropic's ACI principles, this tool is extensively documented with
clear examples and usage patterns.
"""

from typing import Any, Optional

from rhesis.penelope.prompts import TARGET_INTERACTION_TOOL_DESCRIPTION_TEMPLATE
from rhesis.penelope.targets.base import Target
from rhesis.penelope.tools.base import Tool, ToolResult


class TargetInteractionTool(Tool):
    """
    Tool for sending messages to the test target and receiving responses.

    This is your primary tool for testing. Each call represents one turn
    in a multi-turn conversation with the system under test.

    The target can be any system that Penelope can interact with:
    - Rhesis endpoints (HTTP/REST/WebSocket)
    - Other AI agents
    - Complete applications
    - Custom target implementations

    Following Anthropic's ACI design principles:
    - Clear, extensive documentation
    - Real-world examples
    - Edge case handling
    - Natural parameter formats
    """

    def __init__(self, target: Target):
        """
        Initialize the tool with a target.

        Args:
            target: The target to test (implements Target interface)
        """
        self.target = target

    @property
    def name(self) -> str:
        return "send_message_to_target"

    @property
    def description(self) -> str:
        return TARGET_INTERACTION_TOOL_DESCRIPTION_TEMPLATE.format(
            target_documentation=self.target.get_tool_documentation()
        )

    def execute(
        self, message: str = "", session_id: Optional[str] = None, **kwargs: Any
    ) -> ToolResult:
        """
        Execute the target interaction tool.

        Args:
            message: The user message to send (validated via Pydantic)
            session_id: Optional session ID for multi-turn conversations
            **kwargs: Additional target-specific parameters

        Returns:
            ToolResult with the target's response
        """
        try:
            # Send message to target
            response = self.target.send_message(message, session_id, **kwargs)

            # Convert TargetResponse to ToolResult
            if response.success:
                return ToolResult(
                    success=True,
                    output={
                        "response": response.content,
                        "session_id": response.session_id,
                        "metadata": response.metadata,
                    },
                    metadata={
                        "message_sent": message,
                        "session_id_used": session_id,
                        "target_type": self.target.target_type,
                        "target_id": self.target.target_id,
                    },
                )
            else:
                return ToolResult(
                    success=False,
                    output={},
                    error=response.error or "Target interaction failed",
                )

        except Exception as e:
            return ToolResult(
                success=False,
                output={},
                error=f"Unexpected error: {str(e)}",
            )
