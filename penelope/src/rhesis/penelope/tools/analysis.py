"""
Analysis tools for Penelope.

Analysis tools are used to examine, verify, or monitor data during testing,
but do not directly interact with the target. They should be used in conjunction
with target interaction tools, not as replacements for them.
"""

from abc import ABC
from typing import Any, Optional

from rhesis.penelope.tools.base import Tool, ToolResult


class AnalysisTool(Tool, ABC):
    """
    Base class for analysis tools.

    Analysis tools are used to examine responses, verify state, or monitor
    performance during testing. They complement target interaction tools
    but should not replace the conversation flow.

    Key characteristics:
    - They analyze data that already exists (responses, database state, metrics)
    - They do not directly communicate with the target
    - They should be used strategically, not repeatedly on the same data
    - After analysis, the conversation should continue with target interaction

    Examples:
    - Security scanners that analyze responses for vulnerabilities
    - Database verification tools that check data consistency
    - Performance monitors that track API metrics
    - Response analyzers that extract specific information
    """

    @property
    def tool_category(self) -> str:
        """Return the tool category for workflow management."""
        return "analysis"

    @property
    def analysis_type(self) -> str:
        """
        Return the type of analysis this tool performs.

        This is a user-defined string that describes what kind of analysis
        the tool does. Examples: "security", "verification", "monitoring",
        "extraction", "validation", "performance", etc.

        Users can define any analysis type that makes sense for their tool.

        Returns:
            String describing the analysis type
        """
        raise NotImplementedError("Analysis tools must specify their analysis type")

    @property
    def requires_target_response(self) -> bool:
        """
        Whether this tool requires a recent target response to function properly.

        Returns:
            True if the tool needs a target response, False if it can work independently
        """
        return True

    def get_usage_guidance(self) -> str:
        """
        Get guidance on when and how to use this analysis tool.

        Returns:
            String with usage guidance for the LLM
        """
        guidance = f"""
ANALYSIS TOOL: {self.name}
Type: {self.analysis_type}

WORKFLOW GUIDANCE:
1. Use this tool to analyze data after target interactions
2. Do not use repeatedly on the same data
3. After analysis, continue the conversation with send_message_to_target
4. This tool complements but does not replace target interaction

WHEN TO USE:
✓ After receiving a response from the target
✓ To verify or analyze specific data
✓ As part of a broader testing strategy

WHEN NOT TO USE:
✗ Without relevant data to analyze
✗ Repeatedly on the same response/data
✗ As a substitute for target interaction
✗ When no target interaction has occurred yet
"""

        if self.requires_target_response:
            guidance += "\n✗ Without a recent target response to analyze"

        return guidance

    def validate_usage_context(self, context: Optional[dict] = None) -> tuple[bool, str]:
        """
        Validate whether this tool should be used in the current context.

        Args:
            context: Optional context information (e.g., recent responses, turn history)

        Returns:
            Tuple of (is_valid, reason)
        """
        if self.requires_target_response and context:
            # Check if there's a recent target response
            recent_responses = context.get("recent_target_responses", [])
            if not recent_responses:
                return False, f"Tool {self.name} requires a target response but none found"

            # Check if this response was already analyzed by this tool
            analyzed_responses = context.get("analyzed_responses", {})
            tool_analyses = analyzed_responses.get(self.name, set())

            latest_response_id = recent_responses[0].get("id") if recent_responses else None
            if latest_response_id and latest_response_id in tool_analyses:
                return False, f"Response already analyzed by {self.name}"

        return True, "Usage context is valid"

    def execute_with_validation(self, context: Optional[dict] = None, **kwargs: Any) -> ToolResult:
        """
        Execute the tool with built-in validation.

        Args:
            context: Context information for validation
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with validation information
        """
        # Validate usage context
        is_valid, reason = self.validate_usage_context(context)
        if not is_valid:
            return ToolResult(
                success=False,
                output={},
                error=f"Invalid usage: {reason}",
                metadata={
                    "tool_category": self.tool_category,
                    "analysis_type": self.analysis_type,
                    "validation_failed": True,
                    "validation_reason": reason,
                },
            )

        # Execute the actual analysis
        result = self.execute(**kwargs)

        # Enhance metadata with analysis tool information
        if result.metadata is None:
            result.metadata = {}

        result.metadata.update(
            {
                "tool_category": self.tool_category,
                "analysis_type": self.analysis_type,
                "requires_target_response": self.requires_target_response,
            }
        )

        return result


# Note: Specific analysis tool types (SecurityAnalysisTool, VerificationTool, etc.)
# are not part of Penelope core. Users should create their own by inheriting from
# AnalysisTool and implementing the analysis_type property.
#
# Example:
# class SecurityAnalysisTool(AnalysisTool):
#     @property
#     def analysis_type(self) -> str:
#         return "security"
