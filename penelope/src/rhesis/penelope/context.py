"""
Context and state management for Penelope agent.

Handles test state, conversation history, and result tracking.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from rhesis.penelope.schemas import AssistantMessage, ToolMessage


class TestStatus(str, Enum):
    """Status of a test execution."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    TIMEOUT = "timeout"
    MAX_ITERATIONS = "max_iterations"


class Turn(BaseModel):
    """
    Represents a single turn in the test conversation.

    Uses standard message format (OpenAI-compatible) for maximum LLM provider support.
    Each turn contains:
    - Assistant message with tool_calls (Penelope's action)
    - Tool message with results
    - Optional retrieval context
    - Penelope-specific metadata (reasoning, evaluation)
    """

    turn_number: int = Field(description="The turn number (1-indexed)")
    timestamp: datetime = Field(default_factory=datetime.now)

    # Standard message format (OpenAI-compatible)
    assistant_message: AssistantMessage = Field(description="Assistant message with tool_calls")

    tool_message: ToolMessage = Field(description="Tool response message")

    # Optional retrieval context (for RAG systems)
    retrieval_context: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Retrieved context used in this turn (e.g., from RAG systems)",
    )

    # Penelope-specific metadata (not sent to LLM)
    reasoning: str = Field(description="Penelope's internal reasoning for this turn")
    evaluation: Optional[str] = Field(
        default=None, description="Evaluation of progress after this turn"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    @property
    def tool_name(self) -> str:
        """Extract tool name from the assistant's tool_calls."""
        if self.assistant_message.tool_calls and len(self.assistant_message.tool_calls) > 0:
            return self.assistant_message.tool_calls[0].function.name
        return "unknown"

    @property
    def tool_arguments(self) -> Dict[str, Any]:
        """Extract tool arguments from the assistant's tool_calls."""
        if self.assistant_message.tool_calls and len(self.assistant_message.tool_calls) > 0:
            args_str = self.assistant_message.tool_calls[0].function.arguments
            try:
                return json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                return {}
        return {}

    @property
    def tool_result(self) -> Any:
        """Extract tool result from the tool message."""
        content = self.tool_message.content
        try:
            return json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            return content


class TestResult(BaseModel):
    """Result of a test execution."""

    status: TestStatus = Field(description="Final status of the test")
    goal_achieved: bool = Field(description="Whether the test goal was achieved")
    turns_used: int = Field(description="Number of turns executed")
    findings: List[str] = Field(default_factory=list, description="Key findings from the test")
    history: List[Turn] = Field(default_factory=list, description="Complete conversation history")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the test execution"
    )
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate test duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class GoalProgress(BaseModel):
    """Evaluation of progress toward the test goal."""

    goal_achieved: bool = Field(description="Whether the goal is achieved")
    goal_impossible: bool = Field(
        default=False, description="Whether the goal is determined to be impossible"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in the evaluation (0.0 to 1.0)"
    )
    reasoning: str = Field(description="Explanation of the evaluation")
    findings: List[str] = Field(
        default_factory=list, description="Specific findings supporting this evaluation"
    )


@dataclass
class TestContext:
    """
    Context for a test execution.

    Contains all information needed to execute a test, including
    target, instructions, scenario, and resources.
    """

    target_id: str
    target_type: str
    instructions: str
    goal: str
    scenario: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    max_turns: int = 20
    timeout_seconds: Optional[float] = None


@dataclass
class TestState:
    """
    Current state of a test execution.

    Tracks conversation history, turn count, and session information.
    """

    context: TestContext
    turns: List[Turn] = field(default_factory=list)
    current_turn: int = 0
    session_id: Optional[str] = None
    findings: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    def add_turn(
        self,
        reasoning: str,
        assistant_message: AssistantMessage,
        tool_message: ToolMessage,
        evaluation: Optional[str] = None,
        retrieval_context: Optional[List[Dict[str, Any]]] = None,
    ) -> Turn:
        """
        Add a turn to the conversation history.

        Args:
            reasoning: Penelope's internal reasoning for this turn
            assistant_message: Assistant message with tool_calls (Pydantic model)
            tool_message: Tool response message (Pydantic model)
            evaluation: Optional evaluation of progress
            retrieval_context: Retrieved context used in this turn (e.g., from RAG)

        Returns:
            The created Turn object

        Example:
            from rhesis.penelope.schemas import (
                AssistantMessage, MessageToolCall, FunctionCall, ToolMessage
            )

            assistant_message = AssistantMessage(
                content="I will send a test message",
                tool_calls=[
                    MessageToolCall(
                        id="call_123",
                        type="function",
                        function=FunctionCall(
                            name="send_message_to_target",
                            arguments='{"message": "Hello"}'
                        )
                    )
                ]
            )

            tool_message = ToolMessage(
                tool_call_id="call_123",
                name="send_message_to_target",
                content='{"success": true, "output": "Hi there!"}'
            )
        """
        self.current_turn += 1

        turn = Turn(
            turn_number=self.current_turn,
            reasoning=reasoning,
            assistant_message=assistant_message,
            tool_message=tool_message,
            evaluation=evaluation,
            retrieval_context=retrieval_context,
        )

        self.turns.append(turn)
        return turn

    def add_finding(self, finding: str) -> None:
        """Add a finding to the findings list."""
        if finding not in self.findings:
            self.findings.append(finding)

    def get_conversation_messages(self) -> List[Any]:
        """
        Get the conversation messages in native format.

        Returns a flat list of AssistantMessage and ToolMessage objects
        (Pydantic models) representing the entire conversation.

        To convert to dictionaries for API calls, use .model_dump() on each message.

        Returns:
            List of AssistantMessage and ToolMessage objects (alternating)
        """
        messages = []
        for turn in self.turns:
            messages.append(turn.assistant_message)
            messages.append(turn.tool_message)
        return messages

    def to_result(self, status: TestStatus, goal_achieved: bool) -> TestResult:
        """
        Convert the current state to a TestResult.

        Args:
            status: Final status of the test
            goal_achieved: Whether the goal was achieved

        Returns:
            TestResult object
        """
        return TestResult(
            status=status,
            goal_achieved=goal_achieved,
            turns_used=self.current_turn,
            findings=self.findings,
            history=self.turns,
            start_time=self.start_time,
            end_time=datetime.now(),
        )
