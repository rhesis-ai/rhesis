"""
Workflow management for Penelope to prevent infinite loops and ensure proper tool usage.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from rhesis.penelope.context import ToolExecution, ToolType
from rhesis.penelope.tools.analysis import AnalysisTool
from rhesis.penelope.tools.base import Tool


@dataclass
class WorkflowState:
    """Tracks workflow state to prevent infinite loops and guide tool usage."""

    # Track consecutive analysis tool usage
    consecutive_analysis_tools: int = 0
    max_consecutive_analysis: int = 3

    # Track tool usage patterns
    recent_tool_usage: deque = field(default_factory=lambda: deque(maxlen=10))
    tool_usage_count: Dict[str, int] = field(default_factory=dict)

    # Track analysis tool usage per response
    analyzed_responses: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    # Track target interactions
    turns_since_target_interaction: int = 0
    max_turns_without_target: int = 5

    # Recent target responses for analysis context
    recent_target_responses: List[dict] = field(default_factory=list)

    def add_tool_execution(self, execution: ToolExecution) -> None:
        """Record a tool execution in the workflow state."""
        tool_name = execution.tool_name

        # Update recent usage
        self.recent_tool_usage.append(tool_name)
        self.tool_usage_count[tool_name] = self.tool_usage_count.get(tool_name, 0) + 1

        # Track analysis vs target interaction patterns
        if ToolType.is_target_interaction(tool_name):
            self.consecutive_analysis_tools = 0
            self.turns_since_target_interaction = 0

            # Store target response for analysis context
            if execution.tool_result and isinstance(execution.tool_result, dict):
                output = execution.tool_result.get("output", {})
                response_data = {
                    "id": f"response_{len(self.recent_target_responses)}",
                    "content": output.get("response", ""),
                    "metadata": output.get("metadata", {}),
                    "timestamp": execution.timestamp.isoformat() if execution.timestamp else None,
                }
                self.recent_target_responses.append(response_data)
                # Keep only recent responses
                if len(self.recent_target_responses) > 5:
                    self.recent_target_responses.pop(0)
        else:
            # Assume non-target tools are analysis tools
            self.consecutive_analysis_tools += 1
            self.turns_since_target_interaction += 1

            # Track which responses have been analyzed by which tools
            if self.recent_target_responses:
                latest_response_id = self.recent_target_responses[-1]["id"]
                self.analyzed_responses[latest_response_id].add(tool_name)

    def get_analysis_context(self) -> dict:
        """Get context information for analysis tool validation."""
        return {
            "recent_target_responses": self.recent_target_responses,
            "analyzed_responses": dict(self.analyzed_responses),
            "consecutive_analysis_tools": self.consecutive_analysis_tools,
            "turns_since_target_interaction": self.turns_since_target_interaction,
        }


class WorkflowManager:
    """Manages tool execution workflow to prevent infinite loops and guide proper usage."""

    def __init__(self):
        self.state = WorkflowState()

    def validate_tool_usage(self, tool: Tool, **kwargs) -> Tuple[bool, str]:
        """
        Validate whether a tool should be used in the current workflow context.

        Args:
            tool: The tool to validate
            **kwargs: Tool parameters

        Returns:
            Tuple of (is_valid, reason)
        """
        tool_name = tool.name

        # Check for excessive consecutive analysis tools
        if isinstance(tool, AnalysisTool):
            if self.state.consecutive_analysis_tools >= self.state.max_consecutive_analysis:
                return False, (
                    f"Too many consecutive analysis tools ({self.state.consecutive_analysis_tools}). "
                    f"Use send_message_to_target to continue the conversation."
                )

            # Validate analysis tool context
            context = self.state.get_analysis_context()
            is_valid, reason = tool.validate_usage_context(context)
            if not is_valid:
                return False, reason

        # Check for excessive turns without target interaction
        if not ToolType.is_target_interaction(tool_name):
            if self.state.turns_since_target_interaction >= self.state.max_turns_without_target:
                return False, (
                    f"Too many turns without target interaction ({self.state.turns_since_target_interaction}). "
                    f"Use send_message_to_target to continue the conversation."
                )

        # Check for repetitive tool usage patterns
        recent_tools = list(self.state.recent_tool_usage)
        if len(recent_tools) >= 3:
            # Check for immediate repetition (same tool used consecutively)
            if recent_tools[-1] == recent_tools[-2] == tool_name:
                return False, f"Tool {tool_name} used repeatedly. Try a different approach."

            # Check for oscillation pattern (A -> B -> A -> B)
            if (
                len(recent_tools) >= 4
                and recent_tools[-1] == recent_tools[-3] == tool_name
                and recent_tools[-2] == recent_tools[-4]
            ):
                return (
                    False,
                    f"Detected oscillation pattern with {tool_name}. Try a different approach.",
                )

        return True, "Tool usage is valid"

    def get_tool_guidance(self, available_tools: List[Tool]) -> str:
        """
        Get guidance on which tools to use based on current workflow state.

        Args:
            available_tools: List of available tools

        Returns:
            String with tool usage guidance
        """
        guidance = []

        # Analyze current state
        if self.state.turns_since_target_interaction == 0:
            guidance.append("✓ Good: Recent target interaction completed")
        elif self.state.turns_since_target_interaction >= 3:
            guidance.append(
                "⚠ Warning: No target interaction for several turns - consider using send_message_to_target"
            )

        if self.state.consecutive_analysis_tools >= 2:
            guidance.append(
                "⚠ Warning: Multiple consecutive analysis tools - continue conversation with target"
            )

        # Provide specific recommendations
        if self.state.consecutive_analysis_tools >= self.state.max_consecutive_analysis - 1:
            guidance.append(
                "🎯 RECOMMENDATION: Use send_message_to_target to continue the conversation"
            )
        elif self.state.recent_target_responses and self.state.consecutive_analysis_tools == 0:
            # Just had a target interaction, analysis tools are appropriate
            analysis_tools = [t for t in available_tools if isinstance(t, AnalysisTool)]
            if analysis_tools:
                guidance.append("🎯 OPPORTUNITY: Recent target response available for analysis")

        # Tool-specific guidance
        if self.state.recent_target_responses:
            latest_response = self.state.recent_target_responses[-1]
            analyzed_by = self.state.analyzed_responses.get(latest_response["id"], set())

            available_analysis = [
                t.name
                for t in available_tools
                if isinstance(t, AnalysisTool) and t.name not in analyzed_by
            ]
            if available_analysis:
                guidance.append(f"🔍 AVAILABLE ANALYSIS: {', '.join(available_analysis)}")

        return "\n".join(guidance) if guidance else "No specific workflow guidance at this time."

    def record_tool_execution(self, execution: ToolExecution) -> None:
        """Record a tool execution for workflow tracking."""
        self.state.add_tool_execution(execution)

    def reset_state(self) -> None:
        """Reset workflow state (e.g., for new test execution)."""
        self.state = WorkflowState()

    def get_workflow_summary(self) -> dict:
        """Get a summary of the current workflow state."""
        return {
            "consecutive_analysis_tools": self.state.consecutive_analysis_tools,
            "turns_since_target_interaction": self.state.turns_since_target_interaction,
            "recent_tool_usage": list(self.state.recent_tool_usage),
            "tool_usage_count": dict(self.state.tool_usage_count),
            "recent_responses_count": len(self.state.recent_target_responses),
        }
