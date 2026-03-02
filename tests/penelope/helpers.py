"""Shared test helpers for Penelope tests.

Provides reusable factory functions for creating test objects.
Import these helpers in test files instead of duplicating them.
"""

from rhesis.penelope.context import TestState, ToolExecution, Turn
from rhesis.penelope.schemas import (
    AssistantMessage,
    FunctionCall,
    MessageToolCall,
    ToolMessage,
)


def create_tool_execution(tool_name: str, reasoning: str = "Test") -> ToolExecution:
    """Create a ToolExecution for testing.

    Args:
        tool_name: Name of the tool.
        reasoning: Reasoning string for the execution.

    Returns:
        ToolExecution instance with minimal valid data.
    """
    assistant_msg = AssistantMessage(
        content="Test",
        tool_calls=[
            MessageToolCall(
                id=f"call_{tool_name}",
                type="function",
                function=FunctionCall(name=tool_name, arguments="{}"),
            )
        ],
    )
    tool_msg = ToolMessage(
        tool_call_id=f"call_{tool_name}",
        name=tool_name,
        content='{"success": true, "output": {}}',
    )
    return ToolExecution(
        tool_name=tool_name,
        reasoning=reasoning,
        assistant_message=assistant_msg,
        tool_message=tool_msg,
    )


def add_turns_to_state(state: TestState, count: int) -> None:
    """Add N completed turns to a test state.

    Each turn contains a single send_message_to_target execution.

    Args:
        state: TestState to add turns to.
        count: Number of turns to add.
    """
    for i in range(count):
        execution = create_tool_execution("send_message_to_target", reasoning=f"Turn {i + 1}")
        turn = Turn(
            turn_number=i + 1,
            executions=[execution],
            target_interaction=execution,
        )
        state.turns.append(turn)
