"""
Utilities for Penelope agent.

Includes stopping conditions, evaluation helpers, and other utility functions.
"""

import logging
import math
from typing import TYPE_CHECKING, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from rhesis.penelope.context import (
    TOOL_METADATA_KEY,
    TOOL_OUTPUT_KEY,
    TOOL_RESPONSE_KEY,
    TOOL_SUCCESS_KEY,
    ExecutionStatus,
    TestState,
)

if TYPE_CHECKING:
    from rhesis.sdk.metrics.base import MetricResult

# Setup logging
logger = logging.getLogger(__name__)
console = Console()


class StopResult:
    """Structured result from a stopping condition check."""

    # Singleton for "don't stop"
    _CONTINUE = None

    def __init__(
        self,
        status: Optional[ExecutionStatus],
        goal_achieved: bool,
        reason: str,
    ):
        self.status = status
        self.goal_achieved = goal_achieved
        self.reason = reason

    @classmethod
    def continue_(cls) -> "StopResult":
        """Return a sentinel meaning 'do not stop'."""
        if cls._CONTINUE is None:
            cls._CONTINUE = cls.__new__(cls)
            cls._CONTINUE.status = None
            cls._CONTINUE.goal_achieved = False
            cls._CONTINUE.reason = ""
        return cls._CONTINUE

    @property
    def should_stop(self) -> bool:
        return self.status is not None


class StoppingCondition:
    """Base class for stopping conditions."""

    def should_stop(self, state: TestState) -> StopResult:
        """
        Check if the agent should stop.

        Args:
            state: Current test state

        Returns:
            StopResult with status and reason, or StopResult.continue_()
        """
        raise NotImplementedError

    def update_result(self, result: "MetricResult") -> None:
        """Update condition with a new evaluation result. No-op by default."""


class MaxTurnsCondition(StoppingCondition):
    """Stop after maximum number of turns."""

    def __init__(self, max_turns: int):
        self.max_turns = max_turns

    def should_stop(self, state: TestState) -> StopResult:
        if state.current_turn >= self.max_turns:
            return StopResult(
                ExecutionStatus.MAX_TURNS,
                False,
                f"Maximum turns reached ({self.max_turns})",
            )
        return StopResult.continue_()


class MaxToolExecutionsCondition(StoppingCondition):
    """Stop after maximum number of tool executions across all turns."""

    def __init__(self, max_tool_executions: int):
        self.max_tool_executions = max_tool_executions

    def should_stop(self, state: TestState) -> StopResult:
        total_executions = len(state.all_executions)
        if total_executions >= self.max_tool_executions:
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

            return StopResult(ExecutionStatus.FAILURE, False, message)
        return StopResult.continue_()


class TimeoutCondition(StoppingCondition):
    """Stop after timeout."""

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds

    def should_stop(self, state: TestState) -> StopResult:
        from datetime import datetime

        elapsed = (datetime.now() - state.start_time).total_seconds()
        if elapsed >= self.timeout_seconds:
            return StopResult(
                ExecutionStatus.TIMEOUT,
                False,
                f"Timeout reached ({self.timeout_seconds}s)",
            )
        return StopResult.continue_()


class GoalAchievedCondition(StoppingCondition):
    """Stop when goal is achieved or determined impossible."""

    def __init__(
        self,
        result: Optional["MetricResult"] = None,
        max_turns: Optional[int] = None,
        min_turns: Optional[int] = None,
        early_stop_threshold: Optional[float] = None,
        impossible_score_threshold: Optional[float] = None,
    ):
        """
        Initialize with SDK MetricResult.

        Args:
            result: Optional initial MetricResult
            max_turns: Maximum turns configured for the test. Used to compute
                the default early-stop floor.
            min_turns: Explicit minimum turns before early stopping is allowed.
                When set, overrides the threshold-based default.
                Cannot exceed max_turns.
            early_stop_threshold: Fraction of max_turns before early stop
                is allowed (default from PenelopeConfig, typically 0.8).
            impossible_score_threshold: Score below which the goal is
                considered impossible (default from PenelopeConfig,
                typically 0.3).
        """
        from rhesis.penelope.config import PenelopeConfig

        self.result = result
        self.max_turns = max_turns
        self.min_turns = min_turns
        self.early_stop_threshold = (
            early_stop_threshold
            if early_stop_threshold is not None
            else PenelopeConfig.get_early_stop_threshold()
        )
        self.impossible_score_threshold = (
            impossible_score_threshold
            if impossible_score_threshold is not None
            else PenelopeConfig.get_impossible_score_threshold()
        )

    def update_result(self, result: "MetricResult"):
        """Update with new SDK evaluation result."""
        self.result = result

    def _get_early_stop_floor(self, strict: bool = False) -> int:
        """
        Compute minimum turns before early stopping is allowed.

        Args:
            strict: When False (goal achieved), min_turns can lower
                the threshold-based floor, saving remaining budget.
                When True (goal impossible), the floor is always at
                least the threshold fraction, ensuring the agent
                exhausts most of its budget before giving up.

        Returns:
            Minimum number of turns before early stopping
        """
        threshold_floor = (
            max(1, math.ceil(self.max_turns * self.early_stop_threshold))
            if self.max_turns is not None
            else 0
        )

        if self.min_turns is None:
            return threshold_floor

        if strict:
            # Goal impossible: never stop before either floor
            return max(threshold_floor, self.min_turns)

        # Goal achieved: min_turns overrides threshold, capped at max_turns
        floor = self.min_turns
        if self.max_turns is not None:
            floor = min(floor, self.max_turns)
        return floor

    def should_stop(self, state: TestState) -> StopResult:
        """
        Check if we should stop based on SDK evaluation.

        Two early-stop scenarios with different thresholds:
        - Goal achieved: allowed after min_turns (saves remaining budget)
        - Goal impossible: allowed only near max_turns (exhausts attempts)
        """
        if not self.result:
            return StopResult.continue_()

        current_turns = len(state.turns)
        success_floor = self._get_early_stop_floor(strict=False)

        # Enforce minimum turn requirement before goal-achieved early stopping
        if current_turns < success_floor:
            logger.debug(
                f"Early stop blocked: {current_turns}/{success_floor} turns "
                "completed. Continuing test execution."
            )
            return StopResult.continue_()

        # Check if goal achieved (from SDK MetricResult.details)
        if self.result.details.get("is_successful", False):
            reason = self.result.details.get("reason", "Goal achieved")
            return StopResult(ExecutionStatus.SUCCESS, True, f"Goal achieved: {reason}")

        # Check if goal is impossible (very low score after exhausting budget)
        if (
            isinstance(self.result.score, (int, float))
            and self.result.score < self.impossible_score_threshold
        ):
            impossible_floor = self._get_early_stop_floor(strict=True)
            if current_turns >= impossible_floor:
                reason = self.result.details.get("reason", "Low score after multiple attempts")
                return StopResult(
                    ExecutionStatus.FAILURE,
                    False,
                    f"Goal determined impossible: {reason}",
                )
            else:
                logger.debug(
                    f"Low score ({self.result.score:.2f}) but only "
                    f"{current_turns}/{impossible_floor} turns used. "
                    f"Continuing to allow more attempts."
                )

        return StopResult.continue_()


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
    if ToolType.is_target_interaction(action) and result.get(TOOL_SUCCESS_KEY, False):
        output = result.get(TOOL_OUTPUT_KEY, {})
        metadata = result.get(TOOL_METADATA_KEY, {})

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
        response = output.get(TOOL_RESPONSE_KEY, "")
        if response:
            content.append("Response Received: ", style="bold blue")
            # Truncate long responses for display
            display_response = response[:300] + "..." if len(response) > 300 else response
            content.append(f'"{display_response}"\n\n', style="cyan")

    content.append("Result: ", style="bold magenta")
    content.append(f"{result.get(TOOL_SUCCESS_KEY, False)}", style="white")

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
