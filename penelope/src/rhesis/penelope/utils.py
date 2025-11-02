"""
Utilities for Penelope agent.

Includes stopping conditions, evaluation helpers, and other utility functions.
"""

import logging
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from rhesis.penelope.context import GoalProgress, TestState

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

    def __init__(self, progress: Optional[GoalProgress] = None):
        self.progress = progress

    def update_progress(self, progress: GoalProgress):
        """Update the current progress."""
        self.progress = progress

    def should_stop(self, state: TestState) -> tuple[bool, str]:
        if not self.progress:
            return False, ""

        if self.progress.goal_achieved:
            return True, f"Goal achieved: {self.progress.reasoning}"

        if self.progress.goal_impossible:
            return True, f"Goal determined impossible: {self.progress.reasoning}"

        return False, ""


def format_tool_schema_for_llm(tools: List) -> str:
    """
    Format tool schemas in a way that's clear for the LLM.

    Args:
        tools: List of Tool instances

    Returns:
        Formatted string describing available tools
    """
    tool_descriptions = []

    for tool in tools:
        desc = f"**{tool.name}**\n\n{tool.description}\n\n"
        desc += "Parameters:\n"
        for param in tool.parameters:
            required = "REQUIRED" if param.required else "optional"
            desc += f"  - {param.name} ({param.type}, {required}): {param.description}\n"
        desc += "\n"
        tool_descriptions.append(desc)

    return "\n".join(tool_descriptions)


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


def truncate_text(text: str, max_length: int = 200) -> str:
    """
    Truncate text to max length with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def extract_json_from_response(response: str) -> Optional[Dict]:
    """
    Try to extract JSON from a response that might contain other text.

    Args:
        response: Response text that may contain JSON

    Returns:
        Extracted JSON dict or None
    """
    import json
    import re

    # Try to find JSON in the response
    json_match = re.search(r"\{.*\}", response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None
