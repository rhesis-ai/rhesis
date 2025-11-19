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

    def is_target_interaction_tool(self) -> bool:
        """This tool represents a target interaction and counts as a turn."""
        return True

    @property
    def description(self) -> str:
        return TARGET_INTERACTION_TOOL_DESCRIPTION_TEMPLATE.format(
            target_documentation=self.target.get_tool_documentation()
        )

    def execute(
        self, message: str = "", conversation_id: Optional[str] = None, **kwargs: Any
    ) -> ToolResult:
        """
        Execute the target interaction tool.

        Args:
            message: The user message to send (validated via Pydantic)
            conversation_id: Optional conversation ID for multi-turn conversations
            **kwargs: Additional target-specific parameters, including other conversation
                     tracking fields (thread_id, chat_id, etc.)

        Returns:
            ToolResult with the target's response
        """
        try:
            # Extract conversation ID from any supported field
            from rhesis.penelope.conversation import (
                CONVERSATION_FIELD_NAMES,
                extract_conversation_id,
            )

            # Build params dict with all conversation fields
            params = kwargs.copy()
            if conversation_id:
                params["conversation_id"] = conversation_id

            # Extract the actual conversation ID from any field
            final_conversation_id = extract_conversation_id(params)

            # Send message to target (conversation_id is passed as positional arg, not in kwargs)
            # Remove conversation fields from params to avoid duplication
            target_params = {k: v for k, v in params.items() if k not in CONVERSATION_FIELD_NAMES}
            response = self.target.send_message(message, final_conversation_id, **target_params)

            # Convert TargetResponse to ToolResult
            if response.success:
                from rhesis.penelope.conversation import get_conversation_field_name

                # Determine which conversation field was used
                conv_field_name = get_conversation_field_name(params) or "conversation_id"

                output = {
                    "response": response.content,
                    "metadata": response.metadata,
                }

                # Add conversation ID with the appropriate field name (even if None)
                conversation_value = response.conversation_id
                output[conv_field_name] = conversation_value

                return ToolResult(
                    success=True,
                    output=output,
                    metadata={
                        "message_sent": message,
                        "conversation_id_used": final_conversation_id,
                        "conversation_field_name": conv_field_name,
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
