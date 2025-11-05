"""
Context and state management for Penelope agent.

Handles test state, conversation history, and result tracking.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer

from rhesis.penelope.schemas import AssistantMessage, CriterionEvaluation, ToolMessage


class ExecutionStatus(str, Enum):
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

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime, _info):
        """Serialize datetime to ISO format string."""
        return timestamp.isoformat()

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


class GoalEvaluationResult(BaseModel):
    """
    Structured goal evaluation results.

    Preserves the criterion-by-criterion evaluation from the LLM in machine-readable format,
    enabling programmatic analysis, filtering, and aggregation of test results.
    """

    turn_count: int = Field(description="Number of turns at evaluation time")
    criteria_evaluations: List[CriterionEvaluation] = Field(
        description="Detailed evaluation of each criterion"
    )
    all_criteria_met: bool = Field(description="Whether all criteria were met")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the evaluation")
    reasoning: str = Field(description="Summary explanation of the evaluation")
    evidence: List[str] = Field(
        default_factory=list, description="Supporting evidence from the conversation"
    )
    evaluated_at: datetime = Field(
        default_factory=datetime.now, description="When the evaluation was performed"
    )

    @field_serializer("evaluated_at", when_used="json")
    def serialize_evaluated_at(self, dt: datetime, _info):
        """Serialize datetime to ISO format string."""
        return dt.isoformat()


class TestResult(BaseModel):
    """Result of a test execution."""

    status: ExecutionStatus = Field(description="Final status of the test")
    goal_achieved: bool = Field(description="Whether the test goal was achieved")
    turns_used: int = Field(description="Number of turns executed")
    findings: List[str] = Field(default_factory=list, description="Key findings from the test")
    history: List[Turn] = Field(default_factory=list, description="Complete conversation history")

    # Structured evaluation data (machine-readable)
    goal_evaluation: Optional[GoalEvaluationResult] = Field(
        default=None,
        description="Structured goal evaluation with criterion-by-criterion results",
    )

    # Metrics in standard format (compatible with SDK single-turn metrics)
    metrics: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "Evaluation metrics in standard format. Includes goal achievement metric "
            "and any additional SDK metrics that were computed. Format matches single-turn "
            "metrics for consistency across the platform."
        ),
    )

    # Test configuration (for reproducibility and analysis)
    test_configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Complete test configuration including goal, instructions, scenario, "
            "context, max_turns, and other parameters used for this test execution."
        ),
    )

    # Model information (for model comparison and analytics)
    model_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Information about the LLM model used: name, provider, version, "
            "temperature, and other model-specific configuration."
        ),
    )

    # Target information (for endpoint analytics)
    target_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Information about the target being tested: endpoint_id, type, URL, "
            "and other target-specific details."
        ),
    )

    # Execution statistics (for performance analysis)
    execution_stats: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Execution statistics including token usage, costs, timing per turn, "
            "tool usage statistics, and other performance metrics."
        ),
    )

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

    @field_serializer("start_time", "end_time", when_used="json")
    def serialize_datetime(self, dt: Optional[datetime], _info):
        """Serialize datetime to ISO format string."""
        return dt.isoformat() if dt else None


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

    # Structured evaluation data (optional, when available from LLM evaluation)
    structured_evaluation: Optional[GoalEvaluationResult] = Field(
        default=None,
        description="Structured criterion-by-criterion evaluation results",
    )


@dataclass
class TestContext:
    """
    Context for a test execution.

    Contains all information needed to execute a test, including
    target, instructions, scenario, restrictions, and resources.
    """

    target_id: str
    target_type: str
    instructions: str
    goal: str
    scenario: Optional[str] = None
    restrictions: Optional[str] = None
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

    # Store the last goal evaluation result (structured)
    last_evaluation: Optional[GoalEvaluationResult] = None

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

    def to_result(
        self,
        status: ExecutionStatus,
        goal_achieved: bool,
        target: Optional[Any] = None,
        model: Optional[Any] = None,
    ) -> TestResult:
        """
        Convert the current state to a TestResult.

        Args:
            status: Final status of the test
            goal_achieved: Whether the goal was achieved
            target: Optional target object for extracting target_info
            model: Optional model object for extracting model_info

        Returns:
            TestResult object with complete execution data including structured evaluation
        """
        # Generate concise findings summary from final evaluation
        findings = self._generate_findings_summary(status, goal_achieved)

        # Generate metrics in standard format
        metrics = self._generate_metrics(goal_achieved)

        # Build test configuration
        test_configuration = {
            "goal": self.context.goal,
            "instructions": self.context.instructions,
            "scenario": self.context.scenario,
            "context": self.context.context,
            "max_turns": self.context.max_turns,
        }

        # Build model info (if model provided)
        model_info = None
        if model:
            model_info = {
                "model_name": getattr(model, "model_name", "unknown"),
                "provider": getattr(model, "provider", "unknown"),
                "temperature": getattr(model, "temperature", None),
                "max_tokens": getattr(model, "max_tokens", None),
            }

        # Build target info (if target provided)
        target_info = None
        if target:
            target_info = {
                "target_id": getattr(target, "target_id", "unknown"),
                "target_type": getattr(target, "target_type", "unknown"),
            }
            # Add endpoint_id if it's an EndpointTarget
            if hasattr(target, "endpoint_id"):
                target_info["endpoint_id"] = target.endpoint_id

        # Build execution statistics
        execution_stats = self._generate_execution_stats()

        return TestResult(
            status=status,
            goal_achieved=goal_achieved,
            turns_used=self.current_turn,
            findings=findings,
            history=self.turns,
            goal_evaluation=self.last_evaluation,
            metrics=metrics,
            test_configuration=test_configuration,
            model_info=model_info,
            target_info=target_info,
            execution_stats=execution_stats,
            start_time=self.start_time,
            end_time=datetime.now(),
        )

    def _generate_findings_summary(self, status: ExecutionStatus, goal_achieved: bool) -> List[str]:
        """
        Generate concise findings summary from the final evaluation state.

        This avoids duplication with goal_evaluation.criteria_evaluations by
        providing only a high-level summary. Detailed criterion data is in
        goal_evaluation.criteria_evaluations.

        Returns:
            List of high-level summary strings
        """
        findings = []

        # If we have structured evaluation, use it for summary
        if self.last_evaluation:
            eval_result = self.last_evaluation
            met_count = sum(1 for c in eval_result.criteria_evaluations if c.met)
            total_count = len(eval_result.criteria_evaluations)

            # Overall status
            if eval_result.all_criteria_met:
                findings.append(f"✓ All criteria met ({met_count}/{total_count})")
            else:
                findings.append(f"✗ Partial success: {met_count}/{total_count} criteria met")

            # Completion info
            findings.append(f"Test completed in {eval_result.turn_count} turn(s)")

            # Confidence level
            confidence_label = (
                "High"
                if eval_result.confidence >= 0.8
                else "Medium"
                if eval_result.confidence >= 0.5
                else "Low"
            )
            findings.append(f"Confidence: {eval_result.confidence:.1f} ({confidence_label})")

            # Add failed criteria summary if any
            failed = [c for c in eval_result.criteria_evaluations if not c.met]
            if failed:
                findings.append(f"Failed criteria: {len(failed)}")
                for criterion in failed:
                    findings.append(f"  • {criterion.criterion}")
        else:
            # Fallback for tests without structured evaluation
            status_icon = "✓" if goal_achieved else "✗"
            findings.append(f"{status_icon} Test {status.value}")
            findings.append(f"Completed in {self.current_turn} turn(s)")

            # Include any findings that were added during execution
            findings.extend(self.findings)

        return findings

    def _generate_metrics(self, goal_achieved: bool) -> Dict[str, Dict[str, Any]]:
        """
        Generate metrics in standard format (compatible with SDK single-turn metrics).

        Converts the goal_evaluation into the platform's standard metrics format.
        Future SDK metrics will be added to this dictionary.

        Args:
            goal_achieved: Whether the goal was achieved

        Returns:
            Dictionary mapping metric names to their results in standard format
        """
        metrics = {}

        # Convert goal evaluation to standard metric format
        if self.last_evaluation:
            eval_result = self.last_evaluation
            met_count = sum(1 for c in eval_result.criteria_evaluations if c.met)
            total_count = len(eval_result.criteria_evaluations)

            # Build detailed reason including criterion breakdown
            reason_parts = [eval_result.reasoning]
            if not eval_result.all_criteria_met:
                failed = [c for c in eval_result.criteria_evaluations if not c.met]
                reason_parts.append(f"\nFailed criteria ({len(failed)}/{total_count}):")
                for criterion in failed:
                    reason_parts.append(f"  • {criterion.criterion}")

            metrics["Goal Achievement"] = {
                "name": "Goal Achievement",
                "score": eval_result.confidence,
                "reason": "\n".join(reason_parts),
                "backend": "penelope",
                "threshold": None,  # No fixed threshold, uses LLM judgment
                "class_name": "GoalAchievementMetric",
                "description": (
                    "Evaluates whether the multi-turn conversation achieved its stated goal "
                    "through criterion-by-criterion assessment."
                ),
                "is_successful": eval_result.all_criteria_met,
                # Additional Penelope-specific fields
                "criteria_met": met_count,
                "criteria_total": total_count,
                "turn_count": eval_result.turn_count,
                "evaluated_at": eval_result.evaluated_at.isoformat(),
            }
        else:
            # Fallback if no evaluation available
            metrics["Goal Achievement"] = {
                "name": "Goal Achievement",
                "score": 0.5,
                "reason": "No detailed evaluation available",
                "backend": "penelope",
                "threshold": None,
                "class_name": "GoalAchievementMetric",
                "description": "Goal achievement evaluation was not performed",
                "is_successful": goal_achieved,
                "turn_count": self.current_turn,
            }

        # Placeholder for future SDK metrics
        # When SDK metrics are computed, they will be added here:
        # metrics["Context Retention"] = {...}
        # metrics["Conversation Coherence"] = {...}
        # metrics["Safety"] = {...}

        return metrics

    def _generate_execution_stats(self) -> Dict[str, Any]:
        """
        Generate execution statistics from turn history.

        Calculates performance metrics including:
        - Per-turn timing (duration of each turn)
        - Total token usage (if available from LLM responses)
        - Tool usage statistics
        - Success rates

        Returns:
            Dictionary with execution statistics
        """
        stats = {}

        # Per-turn timing
        turn_timings = []
        for i, turn in enumerate(self.turns):
            # Calculate turn duration if we have subsequent turn
            if i + 1 < len(self.turns):
                duration = (self.turns[i + 1].timestamp - turn.timestamp).total_seconds()
                turn_timings.append(
                    {
                        "turn_number": turn.turn_number,
                        "duration_seconds": round(duration, 3),
                        "timestamp": turn.timestamp.isoformat(),
                    }
                )

        # For the last turn, calculate from turn timestamp to end
        if self.turns:
            last_turn = self.turns[-1]
            if self.start_time:
                # Use current time as approximate end for last turn
                from datetime import datetime

                duration = (datetime.now() - last_turn.timestamp).total_seconds()
                turn_timings.append(
                    {
                        "turn_number": last_turn.turn_number,
                        "duration_seconds": round(duration, 3),
                        "timestamp": last_turn.timestamp.isoformat(),
                    }
                )

        stats["turn_timings"] = turn_timings

        # Tool usage statistics
        tool_calls = {}
        for turn in self.turns:
            tool_name = turn.tool_name
            if tool_name:
                if tool_name not in tool_calls:
                    tool_calls[tool_name] = {
                        "total_calls": 0,
                        "successful_calls": 0,
                        "failed_calls": 0,
                    }

                tool_calls[tool_name]["total_calls"] += 1

                # Check if tool call was successful
                if isinstance(turn.tool_result, dict):
                    if turn.tool_result.get("success", False):
                        tool_calls[tool_name]["successful_calls"] += 1
                    else:
                        tool_calls[tool_name]["failed_calls"] += 1

        stats["tool_usage"] = tool_calls

        # Overall statistics
        stats["total_turns"] = len(self.turns)
        stats["successful_interactions"] = sum(
            1
            for t in self.turns
            if isinstance(t.tool_result, dict) and t.tool_result.get("success", False)
        )

        # Token usage (placeholder for when LLM responses include token counts)
        # This will be populated when we add token tracking to LLM responses
        stats["token_usage"] = {
            "note": (
                "Token usage tracking to be implemented when LLM responses include token metadata"
            )
        }

        # Cost estimation (placeholder)
        stats["estimated_cost"] = {
            "note": ("Cost estimation to be implemented based on token usage and model pricing")
        }

        return stats
