"""
Target interaction tool for Penelope.

This is Penelope's primary tool for communicating with the system under test.
Following Anthropic's ACI principles, this tool is extensively documented with
clear examples and usage patterns.
"""

from typing import Any, Optional

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
        return f"""Send a message to the test target and receive a response.

{self.target.get_tool_documentation()}

This is your PRIMARY tool for testing. Each call represents one conversational turn
with the system under test.

═══════════════════════════════════════════════════════════════════════════════

WHEN TO USE:
✓ To send user queries/prompts to the endpoint
✓ To continue multi-turn conversations
✓ To test specific inputs or scenarios
✓ To gather responses for analysis

WHEN NOT TO USE:
✗ Don't use for analysis (use analyze_response instead)
✗ Don't use before planning your approach
✗ Don't make calls without clear purpose

═══════════════════════════════════════════════════════════════════════════════

BEST PRACTICES:

1. Read Responses Carefully
   ├─ Always examine the full response before deciding next steps
   ├─ Look for both explicit content and implicit behaviors
   └─ Note any errors, warnings, or unexpected formatting

2. Maintain Conversation Context
   ├─ Use the session_id from previous responses for follow-ups
   ├─ Don't start a new session unless testing fresh conversation
   └─ Session continuity is crucial for multi-turn testing

3. Test Systematically
   ├─ Each message should have a specific testing purpose
   ├─ Build on previous responses naturally
   └─ Avoid repetitive or aimless queries

4. Write Natural Messages
   ├─ Write as a real user would write
   ├─ Avoid test-like language ("Test case 1...")
   └─ Match the tone appropriate for the endpoint

═══════════════════════════════════════════════════════════════════════════════

EXAMPLE USAGE:

# Good Example 1: Initial question
>>> send_message_to_target(
...     message="What's your refund policy for electronics?"
... )
{{
  "response": "Our electronics refund policy allows...",
  "session_id": "abc123",
  "success": true
}}

# Good Example 2: Natural follow-up
>>> send_message_to_target(
...     message="What if I opened the box but didn't use it?",
...     session_id="abc123"
... )
{{
  "response": "If the product is unopened and in original condition...",
  "session_id": "abc123",
  "success": true
}}

# Good Example 3: Testing edge case
>>> send_message_to_target(
...     message="I bought it 6 months ago, can I still return it?"
... )

# Bad Example: Too artificial
>>> send_message_to_target(
...     message="Test Case #1: Refund query validation"
... )

# Bad Example: Template-like
>>> send_message_to_target(
...     message="{{user_input_here}}"
... )

═══════════════════════════════════════════════════════════════════════════════

IMPORTANT NOTES:

⚠ Session Management:
  - First message: Leave session_id empty, you'll get one in response
  - Follow-ups: Always use the session_id from the previous response
  - New conversation: Omit session_id to start fresh
  - Sessions may expire after inactivity (typically 1 hour)

⚠ Error Handling:
  - If success=false, check the error field for details
  - Network errors will be retried automatically (up to 3 times)
  - Invalid requests won't be retried

⚠ Response Format:
  - Always check the "success" field first
  - Response content is in the "response" field
  - Additional metadata may be in "metadata" field

═══════════════════════════════════════════════════════════════════════════════

Remember: Each call costs time and resources. Make every interaction count."""

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
