"""
Utilities for Penelope agent.

Includes stopping conditions, evaluation helpers, and other utility functions.
"""

import logging
from typing import TYPE_CHECKING, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from rhesis.penelope.context import TestState

if TYPE_CHECKING:
    from rhesis.sdk.metrics.base import MetricResult

# Setup logging
logger = logging.getLogger(__name__)
console = Console()


class StoppingCondition:
    """Base class for stopping conditions."""

    def should_stop(self, state: TestState) -> tuple[bool, str]:
        """
        Check if the agent should stop.

        Args:
            state: Current test state

        Returns:
            Tuple of (should_stop, reason)
        """
        raise NotImplementedError


class MaxTurnsCondition(StoppingCondition):
    """Stop after maximum number of turns."""

    def __init__(self, max_turns: int):
        self.max_turns = max_turns

    def should_stop(self, state: TestState) -> tuple[bool, str]:
        if state.current_turn >= self.max_turns:
            return True, f"Maximum turns reached ({self.max_turns})"
        return False, ""


class MaxToolExecutionsCondition(StoppingCondition):
    """Stop after maximum number of tool executions across all turns."""

    def __init__(self, max_tool_executions: int):
        self.max_tool_executions = max_tool_executions

    def should_stop(self, state: TestState) -> tuple[bool, str]:
        total_executions = len(state.all_executions)
        if total_executions >= self.max_tool_executions:
            # Calculate statistics for helpful error message
            avg_tools_per_turn = total_executions / max(state.current_turn, 1)

            message = (
                f"Maximum tool executions reached "
                f"({total_executions}/{self.max_tool_executions}).\n\n"
                "This limit prevents infinite loops and runaway costs.\n\n"
                "Current execution breakdown:\n"
                f"- Turns completed: {state.current_turn}\n"
                f"- Tool executions: {total_executions}\n"
                f"- Average tools per turn: {avg_tools_per_turn:.1f}\n\n"
                "To increase this limit:\n"
                "1. Via parameter: PenelopeAgent(..., max_tool_executions=100)\n"
                "2. Via environment: export PENELOPE_MAX_TOOL_EXECUTIONS=100\n\n"
                "Warning: Higher limits increase cost risk. "
                "Ensure your agent is making progress."
            )

            return True, message
        return False, ""


class TimeoutCondition(StoppingCondition):
    """Stop after timeout."""

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds

    def should_stop(self, state: TestState) -> tuple[bool, str]:
        from datetime import datetime

        elapsed = (datetime.now() - state.start_time).total_seconds()
        if elapsed >= self.timeout_seconds:
            return True, f"Timeout reached ({self.timeout_seconds}s)"
        return False, ""


class GoalAchievedCondition(StoppingCondition):
    """Stop when goal is achieved or determined impossible."""

    # Fraction of max_turns that must complete before goal-achieved early stop
    EARLY_STOP_THRESHOLD = 0.8

    def __init__(
        self,
        result: Optional["MetricResult"] = None,
        max_turns: Optional[int] = None,
        min_turns: Optional[int] = None,
    ):
        """
        Initialize with SDK MetricResult.

        Args:
            result: Optional initial MetricResult
            max_turns: Maximum turns configured for the test. Used to compute
                the default early-stop floor (80% of max_turns).
            min_turns: Explicit minimum turns before early stopping is allowed.
                When set, overrides the 80% default. Cannot exceed max_turns.
        """
        self.result = result
        self.max_turns = max_turns
        self.min_turns = min_turns

    def update_result(self, result: "MetricResult"):
        """Update with new SDK evaluation result."""
        self.result = result

    def _get_min_turns_before_stop(self) -> int:
        """
        Compute the minimum number of turns before early stopping is allowed.

        Priority:
        1. Explicit min_turns parameter (capped at max_turns)
        2. Fraction of max_turns (EARLY_STOP_THRESHOLD, default 80%)
        3. Fallback to 0 (no floor, for backward compatibility)

        Returns:
            Minimum number of turns before early stopping
        """
        if self.min_turns is not None:
            # Explicit min_turns, but never exceed max_turns
            if self.max_turns is not None:
                return min(self.min_turns, self.max_turns)
            return self.min_turns
        if self.max_turns is not None:
            return max(1, int(self.max_turns * self.EARLY_STOP_THRESHOLD))
        return 0

    def should_stop(self, state: TestState) -> tuple[bool, str]:
        """
        Check if we should stop based on SDK evaluation.

        Early stopping (goal achieved or impossible) is only allowed after
        completing the minimum turn requirement, ensuring the agent exercises
        the conversation fully.

        Note: This accesses the MetricResult object directly (which has
        .score and .details). This is different from the flattened metrics
        in TestResult.metrics (output format).
        """
        if not self.result:
            return False, ""

        current_turns = len(state.turns)
        min_turns = self._get_min_turns_before_stop()

        # Enforce minimum turn requirement before any early stopping
        if current_turns < min_turns:
            logger.debug(
                f"Early stop blocked: {current_turns}/{min_turns} turns "
                "completed. Continuing test execution."
            )
            return False, ""

        # Check if goal achieved (from SDK MetricResult.details)
        if self.result.details.get("is_successful", False):
            reason = self.result.details.get("reason", "Goal achieved")
            return True, f"Goal achieved: {reason}"

        # Check if goal is impossible (very low score after sufficient attempts)
        if isinstance(self.result.score, (int, float)) and self.result.score < 0.3:
            reason = self.result.details.get("reason", "Low score after multiple attempts")
            return True, f"Goal determined impossible: {reason}"

        return False, ""


def display_turn(turn_number: int, reasoning: str, action: str, result: Dict):
    """
    Display a turn in a nice formatted way using Rich.

    Args:
        turn_number: The turn number
        reasoning: Penelope's reasoning
        action: The action taken
        result: The result from the tool
    """
    from rhesis.penelope.context import ToolType

    # Create panel content
    content = Text()
    content.append(f"Turn {turn_number}\n\n", style="bold cyan")
    content.append("Reasoning: ", style="bold yellow")
    content.append(f"{reasoning}\n\n", style="white")
    content.append("Action: ", style="bold green")
    content.append(f"{action}\n\n", style="white")

    # Show message sent and response received for target interaction tools
    if ToolType.is_target_interaction(action) and result.get("success", False):
        output = result.get("output", {})
        metadata = result.get("metadata", {})

        # Extract message sent (from metadata)
        message_sent = metadata.get("message_sent")
        if message_sent:
            content.append("Message Sent: ", style="bold blue")
            # Truncate long messages for display
            display_message = (
                message_sent[:200] + "..." if len(message_sent) > 200 else message_sent
            )
            content.append(f'"{display_message}"\n\n', style="cyan")

        # Show conversation ID if present
        from rhesis.penelope.conversation import extract_conversation_id

        # Try to extract conversation ID from multiple sources
        conversation_id = (
            metadata.get("conversation_id_used")  # What was sent to target
            or extract_conversation_id(output)  # What came back from target
            or extract_conversation_id(metadata)  # Fallback to metadata
        )

        if conversation_id:
            content.append("Conversation ID: ", style="bold blue")
            content.append(f"{conversation_id}\n\n", style="white")
        elif metadata.get("conversation_field_name"):
            # Show that conversation tracking was attempted but no ID found
            content.append("Conversation ID: ", style="bold blue")
            content.append("None\n\n", style="dim white")

        # Extract response received
        response = output.get("response", "")
        if response:
            content.append("Response Received: ", style="bold blue")
            # Truncate long responses for display
            display_response = response[:300] + "..." if len(response) > 300 else response
            content.append(f'"{display_response}"\n\n', style="cyan")

    content.append("Result: ", style="bold magenta")
    content.append(f"{result.get('success', False)}", style="white")

    panel = Panel(content, title="Penelope's Turn", border_style="blue")
    console.print(panel)


def display_test_result(result):
    """
    Display final test result in a formatted way.

    Args:
        result: TestResult object
    """
    from rich.table import Table

    border_style = "green" if result.goal_achieved else "red"
    table = Table(title="Test Results", show_header=False, border_style=border_style)

    table.add_row("Status", str(result.status.value))
    table.add_row("Goal Achieved", "Yes" if result.goal_achieved else "No")
    table.add_row("Turns Used", str(result.turns_used))

    if result.duration_seconds:
        table.add_row("Duration", f"{result.duration_seconds:.2f}s")

    console.print("\n")
    console.print(table)

    if result.findings:
        console.print("\n[bold]Findings:[/bold]")
        for i, finding in enumerate(result.findings, 1):
            console.print(f"  {i}. {finding}")
