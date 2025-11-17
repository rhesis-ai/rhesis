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


class MaxIterationsCondition(StoppingCondition):
    """Stop after maximum number of iterations."""

    def __init__(self, max_iterations: int):
        self.max_iterations = max_iterations

    def should_stop(self, state: TestState) -> tuple[bool, str]:
        if state.current_turn >= self.max_iterations:
            return True, f"Maximum iterations reached ({self.max_iterations})"
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

    def __init__(self, result: Optional["MetricResult"] = None):
        """Initialize with SDK MetricResult."""
        self.result = result

    def update_result(self, result: "MetricResult"):
        """Update with new SDK evaluation result."""
        self.result = result

    def should_stop(self, state: TestState) -> tuple[bool, str]:
        """
        Check if we should stop based on SDK evaluation.

        Note: This accesses the MetricResult object directly (which has .score and .details).
        This is different from the flattened metrics in TestResult.metrics (output format).
        """
        if not self.result:
            return False, ""

        # Check if goal achieved (from SDK MetricResult.details)
        if self.result.details.get("is_successful", False):
            reason = self.result.details.get("reason", "Goal achieved")
            return True, f"Goal achieved: {reason}"

        # Check if goal is impossible (Penelope's stopping logic)
        # Give up after 5+ tool executions with very low score
        if (
            len(state.turns) >= 5
            and isinstance(self.result.score, (int, float))
            and self.result.score < 0.3
        ):
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
    # Create panel content
    content = Text()
    content.append(f"Turn {turn_number}\n\n", style="bold cyan")
    content.append("Reasoning: ", style="bold yellow")
    content.append(f"{reasoning}\n\n", style="white")
    content.append("Action: ", style="bold green")
    content.append(f"{action}\n\n", style="white")

    # Show message sent and response received for target interaction
    if action == "send_message_to_target" and result.get("success", False):
        output = result.get("output", {})

        # Extract message sent (from metadata or try to get from tool args)
        message_sent = None
        if "metadata" in result:
            message_sent = result["metadata"].get("message_sent")

        if message_sent:
            content.append("Message Sent: ", style="bold blue")
            # Truncate long messages for display
            display_message = (
                message_sent[:200] + "..." if len(message_sent) > 200 else message_sent
            )
            content.append(f'"{display_message}"\n\n', style="cyan")

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
    table.add_row("Goal Achieved", "✓ Yes" if result.goal_achieved else "✗ No")
    table.add_row("Turns Used", str(result.turns_used))

    if result.duration_seconds:
        table.add_row("Duration", f"{result.duration_seconds:.2f}s")

    console.print("\n")
    console.print(table)

    if result.findings:
        console.print("\n[bold]Findings:[/bold]")
        for i, finding in enumerate(result.findings, 1):
            console.print(f"  {i}. {finding}")
