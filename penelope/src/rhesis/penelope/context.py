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

from rhesis.penelope.schemas import AssistantMessage, ConversationHistory, ToolMessage


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

    A turn is defined as one Penelope-target interaction using target interaction tools:
    - Penelope sends a message to the target (via send_message_to_target or similar tools)
    - Target responds with a message

    This creates one user-assistant message pair in the conversation history.

    IMPORTANT: Only target interaction tools count as turns. Internal tools
    (analyze_response, extract_information, etc.) are tracked but do not increment
    the turn counter as they don't represent interactions with the system under test.

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


class ConversationTurn(BaseModel):
    """
    Simplified conversation turn for easy reading and UI display.

    Extracts the key conversation elements from the detailed history
    with clear role names (penelope/target) for better understanding.
    """

    turn: int = Field(description="Turn number (1-indexed)")
    timestamp: str = Field(description="ISO timestamp when the turn occurred")
    penelope_reasoning: str = Field(description="Penelope's reasoning for this turn")
    penelope_message: str = Field(description="Message sent by Penelope to the target")
    target_response: str = Field(description="Response received from the target endpoint")
    session_id: Optional[str] = Field(
        default=None, description="Session ID for multi-turn conversations"
    )
    success: bool = Field(description="Whether the tool call was successful")


class TestResult(BaseModel):
    """Result of a test execution."""

    status: ExecutionStatus = Field(description="Final status of the test")
    goal_achieved: bool = Field(description="Whether the test goal was achieved")
    turns_used: int = Field(description="Number of turns executed")
    findings: List[str] = Field(default_factory=list, description="Key findings from the test")
    history: List[Turn] = Field(default_factory=list, description="Complete conversation history")

    # Easy-to-read conversation summary (for UI display and quick understanding)
    conversation_summary: List[ConversationTurn] = Field(
        default_factory=list,
        description=(
            "Simplified conversation flow with clear penelope/target roles. "
            "Provides easy-to-read turn-by-turn summary for UI display and quick analysis. "
            "Complements the detailed 'history' field which contains full technical data."
        ),
    )

    # Structured evaluation data (machine-readable) - Flattened metric dict
    goal_evaluation: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Complete goal evaluation data from GoalAchievementJudge. "
            "Contains detailed criteria_evaluations, reasoning, and evidence. "
            "This is the primary source for detailed goal evaluation data, "
            "while test_metrics contains only summary information to avoid duplication."
        ),
    )

    # Metrics in standard format (compatible with SDK single-turn metrics)
    metrics: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "Evaluation metrics in standard format. For goal evaluation metrics, "
            "contains summary data only (score, confidence, criteria counts) to avoid "
            "duplication with goal_evaluation field. Other metrics contain full data. "
            "Format matches single-turn metrics for consistency across the platform."
        ),
    )

    # Test configuration (for reproducibility and analysis)
    test_configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Complete test configuration including goal, instructions, scenario, "
            "restrictions, context, max_turns, and other parameters used for this test execution."
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
    Uses SDK's ConversationHistory for zero-conversion metric evaluation.

    Turn counting:
    - current_turn: Number of Penelope-target interactions (target interaction tools only)
    - len(turns): Total tool executions (includes internal tools for display/debugging)
    - len(conversation): Number of messages in SDK conversation (1 per target interaction)
    - Each turn = 1 target interaction tool call = 1 conversation message
    - Internal tools are tracked but don't increment current_turn or add to conversation
    """

    context: TestContext
    turns: List[Turn] = field(default_factory=list)

    # Native SDK conversation tracking - built incrementally as tools execute
    conversation: ConversationHistory = field(
        default_factory=lambda: ConversationHistory.from_messages([])
    )

    current_turn: int = 0  # Target interaction turns only
    execution_count: int = 0  # Total tool executions (for display/debugging)
    session_id: Optional[str] = None
    findings: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    # Store SDK metric evaluation results (supports multiple metrics)
    metric_results: List[Any] = field(default_factory=list)  # List of SDK MetricResults

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

        Only target interaction tools (those that communicate with the system under test)
        increment the turn counter. Internal tools (analysis, extraction, etc.) are tracked
        but don't count as turns.

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
        # Increment execution counter for all tool executions (for display/debugging)
        self.execution_count += 1

        # Determine if this is a target interaction tool (counts as a turn)
        tool_name = ""
        if assistant_message.tool_calls and len(assistant_message.tool_calls) > 0:
            tool_name = assistant_message.tool_calls[0].function.name

        # Only increment turn counter for target interaction tools
        is_target_interaction = self._is_target_interaction_tool(tool_name)
        if is_target_interaction:
            self.current_turn += 1

        turn = Turn(
            turn_number=self.execution_count,  # Sequential execution number for display
            reasoning=reasoning,
            assistant_message=assistant_message,
            tool_message=tool_message,
            evaluation=evaluation,
            retrieval_context=retrieval_context,
        )

        self.turns.append(turn)

        # Only update conversation for target interactions (SDK metrics)
        if is_target_interaction:
            self._update_conversation_from_turn(turn)

        return turn

    def _is_target_interaction_tool(self, tool_name: str) -> bool:
        """
        Determine if a tool name represents a target interaction (counts as a turn).

        Target interaction tools are those that communicate with the system under test.
        Internal tools (analysis, extraction, etc.) do not count as turns.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if this tool interacts with the target, False for internal tools
        """
        # List of known target interaction tool names
        # Future target interaction tools should be added here
        target_interaction_tools = {
            "send_message_to_target",
            # Add future target interaction tools here
            # "invoke_api_endpoint",
            # "send_webhook",
            # etc.
        }

        return tool_name in target_interaction_tools

    def _update_conversation_from_turn(self, turn: Turn) -> None:
        """
        Update the conversation history from a turn's tool interaction.

        For send_message_to_target turns, creates a single conversation entry
        that represents the complete Penelope-target interaction as one turn.

        This ensures that SDK metrics see 1 conversation entry per Penelope turn,
        making turn counting consistent between Penelope and SDK evaluations.

        Args:
            turn: The turn to extract conversation from
        """
        from rhesis.penelope.schemas import UserMessage

        # Only process send_message_to_target turns
        if turn.tool_name == "send_message_to_target":
            # Extract user message and assistant response
            user_msg = turn.tool_arguments.get("message", "")

            result = turn.tool_result
            assistant_resp = ""
            if isinstance(result, dict) and result.get("success"):
                resp = result.get("output", {})
                assistant_resp = resp.get("response", "") if isinstance(resp, dict) else str(resp)

            # Create a single conversation entry that represents the complete turn
            # Format: "User: {message}\n\nAssistant: {response}"
            if user_msg and assistant_resp:
                turn_content = f"User: {user_msg}\n\nAssistant: {assistant_resp}"
                self.conversation.messages.append(UserMessage(role="user", content=turn_content))

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
            "restrictions": self.context.restrictions,
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

        # Generate conversation summary
        conversation_summary = self._generate_conversation_summary()

        # Flatten goal_evaluation for frontend compatibility
        # Frontend expects flat structure with all fields at top level, not nested {score, details}
        goal_evaluation_flat = None
        if self.metric_results:
            goal_evaluation_flat = self._flatten_metric_result(self.metric_results[0])

            # Add metric reference for traceability (already in flattened result)
            # The metric name is already included in the flattened result

        return TestResult(
            status=status,
            goal_achieved=goal_achieved,
            turns_used=self.current_turn,
            findings=findings,
            history=self.turns,
            conversation_summary=conversation_summary,
            # Use flattened first metric result for backward compatibility
            goal_evaluation=goal_evaluation_flat,
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
        goal_evaluation (which is a flattened dict with all fields at top level).

        Returns:
            List of high-level summary strings
        """
        findings = []

        # If we have SDK metric evaluations, use first one (goal achievement) for summary
        if self.metric_results:
            first_metric = self.metric_results[0]
            details = first_metric.details
            criteria_evals = details.get("criteria_evaluations", [])

            if criteria_evals:
                # Count met vs total criteria
                met_count = sum(1 for c in criteria_evals if c.get("met", False))
                total_count = len(criteria_evals)

                # Overall status
                all_met = details.get("all_criteria_met", False)
                if all_met:
                    findings.append(f"✓ All criteria met ({met_count}/{total_count})")
                else:
                    findings.append(f"✗ Partial success: {met_count}/{total_count} criteria met")

                # Completion info - use Penelope's actual turn count (tool executions)
                # This represents the number of Penelope-target interactions
                findings.append(f"Test completed in {self.current_turn} turn(s)")

                # Confidence level
                confidence = details.get("confidence", 0.5)
                confidence_label = (
                    "High" if confidence >= 0.8 else "Medium" if confidence >= 0.5 else "Low"
                )
                findings.append(f"Confidence: {confidence:.1f} ({confidence_label})")

                # Add failed criteria summary if any
                failed = [c for c in criteria_evals if not c.get("met", False)]
                if failed:
                    findings.append(f"Failed criteria: {len(failed)}")
                    for criterion in failed:
                        findings.append(f"  • {criterion.get('criterion', 'Unknown')}")
        else:
            # Fallback for tests without structured evaluation
            status_icon = "✓" if goal_achieved else "✗"
            findings.append(f"{status_icon} Test {status.value}")
            findings.append(f"Completed in {self.current_turn} turn(s)")

            # Include any findings that were added during execution
            findings.extend(self.findings)

        return findings

    def _flatten_metric_result(self, metric_result: Any) -> Dict[str, Any]:
        """
        Flatten a MetricResult into frontend-compatible format.

        Converts MetricResult's nested {score, details} structure into a flat dict
        with all details fields at the top level.

        Args:
            metric_result: SDK MetricResult object

        Returns:
            Flattened dictionary with score and all details fields at top level
        """
        # Use model_dump to get all data from the MetricResult
        dumped = metric_result.model_dump()

        # Merge score and details for flat structure expected by frontend
        metric_dict = {
            "score": dumped["score"],
            **dumped["details"],  # Spread all details fields
        }

        # Add convenience fields for criteria-based metrics
        criteria_evals = metric_dict.get("criteria_evaluations", [])
        if criteria_evals:
            met_count = sum(1 for c in criteria_evals if c.get("met", False))
            metric_dict["criteria_met"] = met_count
            metric_dict["criteria_total"] = len(criteria_evals)

        return metric_dict

    def _generate_metrics(self, goal_achieved: bool) -> Dict[str, Dict[str, Any]]:
        """
        Generate metrics in frontend-compatible format.

        For goal achievement metrics, creates a simplified summary version to avoid
        duplication with test_output.goal_evaluation. Other metrics get full data.

        Args:
            goal_achieved: Whether the goal was achieved (unused - kept for compatibility)

        Returns:
            Dictionary mapping metric display names to metric data
        """
        if not self.metric_results:
            return {}

        metrics = {}

        for i, metric_result in enumerate(self.metric_results):
            # Flatten the metric result
            metric_dict = self._flatten_metric_result(metric_result)

            # Extract display name from details
            metric_name = metric_dict.get("name", "penelope_goal_evaluation")
            display_name = " ".join(word.capitalize() for word in metric_name.split("_"))

            # Check if this is a goal achievement metric using stored property
            # Fall back to name check for backward compatibility
            is_goal_metric = metric_dict.get("is_goal_achievement_metric", False)
            if not is_goal_metric:
                # Fallback: check by name for backward compatibility
                is_goal_metric = metric_name == "penelope_goal_evaluation"

            # For goal achievement metrics, create simplified summary version
            # to avoid duplication with test_output.goal_evaluation
            if is_goal_metric:
                metrics[display_name] = self._create_goal_metric_summary(metric_dict)
            else:
                # Other metrics get full data
                metrics[display_name] = metric_dict

        return metrics

    def _create_goal_metric_summary(self, full_metric_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a simplified summary version of goal achievement metric.

        Excludes detailed fields that are duplicated in test_output.goal_evaluation
        to reduce data duplication while maintaining essential metric information.

        Args:
            full_metric_dict: Complete flattened metric dictionary

        Returns:
            Simplified metric dictionary with summary fields only
        """
        # Essential fields for metrics overview
        summary_fields = {
            "score",
            "confidence",
            "criteria_met",
            "criteria_total",
            "is_successful",
            "reason",
            "name",
            "max_score",
            "min_score",
            "threshold",
            "threshold_operator",
            "score_type",
        }

        # Create summary by including only essential fields
        summary = {key: value for key, value in full_metric_dict.items() if key in summary_fields}

        return summary

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

    def _generate_conversation_summary(self) -> List[ConversationTurn]:
        """
        Generate a simplified conversation summary from the detailed history.

        Only includes target interaction turns (those that count as turns).
        Internal tool usage is not included in the conversation summary.

        Extracts key conversation elements with clear penelope/target roles
        for easy reading and UI display.

        Returns:
            List of ConversationTurn objects with simplified conversation flow
        """
        summary = []

        for turn in self.turns:
            # Only include target interaction turns in the conversation summary
            tool_name = turn.tool_name
            if not self._is_target_interaction_tool(tool_name):
                continue
            # Extract Penelope's message from the tool call arguments
            penelope_message = ""
            session_id = None

            if turn.assistant_message.tool_calls:
                tool_call = turn.assistant_message.tool_calls[0]
                if tool_call.function.name == "send_message_to_target":
                    try:
                        args = json.loads(tool_call.function.arguments)
                        penelope_message = args.get("message", "")
                        session_id = args.get("session_id")
                    except (json.JSONDecodeError, KeyError):
                        penelope_message = "Unable to parse message"

            # Extract target response from tool message
            target_response = ""
            success = False

            try:
                tool_content = json.loads(turn.tool_message.content)
                success = tool_content.get("success", False)

                if success and "output" in tool_content:
                    output = tool_content["output"]
                    if isinstance(output, dict):
                        target_response = output.get("response", "")
                    else:
                        target_response = str(output)
                else:
                    error = tool_content.get("error", "Unknown error")
                    target_response = f"Error: {error}"

            except (json.JSONDecodeError, KeyError, AttributeError):
                target_response = "Unable to parse response"

            # Create conversation turn (use execution number for display consistency)
            conversation_turn = ConversationTurn(
                turn=turn.turn_number,  # This is now execution_count
                timestamp=turn.timestamp.isoformat(),
                penelope_reasoning=turn.reasoning,
                penelope_message=penelope_message,
                target_response=target_response,
                session_id=session_id,
                success=success,
            )

            summary.append(conversation_turn)

        return summary
