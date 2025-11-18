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


class ToolType(str, Enum):
    """
    Enumeration of tool types for reliable tool classification.

    This provides type safety and prevents hard-coded string comparisons.
    """

    # Target interaction tools (complete turns)
    SEND_MESSAGE_TO_TARGET = "send_message_to_target"
    INVOKE_API_ENDPOINT = "invoke_api_endpoint"
    SEND_WEBHOOK = "send_webhook"

    # Internal analysis tools (within turns)
    ANALYZE_RESPONSE = "analyze_response"
    EXTRACT_INFORMATION = "extract_information"
    EVALUATE_OUTPUT = "evaluate_output"
    CHECK_API_RESULT = "check_api_result"
    VALIDATE_RESPONSE = "validate_response"

    @classmethod
    def get_target_interaction_tools(cls) -> set[str]:
        """Get all tools that represent target interactions (complete turns)."""
        return {
            cls.SEND_MESSAGE_TO_TARGET,
            cls.INVOKE_API_ENDPOINT,
            cls.SEND_WEBHOOK,
        }

    @classmethod
    def get_internal_tools(cls) -> set[str]:
        """Get all tools that are internal processing (within turns)."""
        return {
            cls.ANALYZE_RESPONSE,
            cls.EXTRACT_INFORMATION,
            cls.EVALUATE_OUTPUT,
            cls.CHECK_API_RESULT,
            cls.VALIDATE_RESPONSE,
        }

    @classmethod
    def is_target_interaction(cls, tool_name: str) -> bool:
        """Check if a tool name represents a target interaction."""
        return tool_name in cls.get_target_interaction_tools()

    @classmethod
    def is_internal_tool(cls, tool_name: str) -> bool:
        """Check if a tool name represents internal processing."""
        return tool_name in cls.get_internal_tools()

    @classmethod
    def generate_tool_description(cls) -> str:
        """Generate dynamic tool description for schema."""
        target_tools = cls.get_target_interaction_tools()
        internal_tools = cls.get_internal_tools()

        desc = "The exact name of the tool to use. Must match one of the available tools:\n"
        desc += "TARGET INTERACTION TOOLS (complete turns):\n"
        for tool in target_tools:
            desc += f"- {tool}: {cls._get_tool_description(tool)}\n"
        desc += "INTERNAL TOOLS (within turns):\n"
        for tool in internal_tools:
            desc += f"- {tool}: {cls._get_tool_description(tool)}\n"
        return desc.rstrip()  # Remove trailing newline

    @classmethod
    def _get_tool_description(cls, tool_name: str) -> str:
        """Get human-readable description for a tool."""
        descriptions = {
            cls.SEND_MESSAGE_TO_TARGET: "Send a message to the target system",
            cls.INVOKE_API_ENDPOINT: "Call an API endpoint directly",
            cls.SEND_WEBHOOK: "Send a webhook request",
            cls.ANALYZE_RESPONSE: "Analyze a response from the target",
            cls.EXTRACT_INFORMATION: "Extract specific information",
            cls.EVALUATE_OUTPUT: "Evaluate the quality of output",
            cls.CHECK_API_RESULT: "Check the result of an API call",
            cls.VALIDATE_RESPONSE: "Validate a response format",
        }
        return descriptions.get(tool_name, "Unknown tool")


class ExecutionStatus(str, Enum):
    """Status of a test execution."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    TIMEOUT = "timeout"
    MAX_ITERATIONS = "max_iterations"


class ToolExecution(BaseModel):
    """
    Represents a single tool execution within a turn.

    A tool execution is one LLM decision → tool call → tool result cycle.
    Multiple tool executions can happen within a single turn.
    """

    tool_name: str = Field(description="Name of the tool that was executed")
    reasoning: str = Field(description="Penelope's reasoning for this tool execution")
    assistant_message: AssistantMessage = Field(description="Assistant message with tool_calls")
    tool_message: ToolMessage = Field(description="Tool response message")
    timestamp: datetime = Field(default_factory=datetime.now)

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime, _info):
        """Serialize datetime to ISO format string."""
        return timestamp.isoformat()

    def get_tool_call_arguments(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the arguments for a specific tool call.

        Args:
            tool_name: Name of the tool to get arguments for. If None, uses self.tool_name.

        Returns:
            Dictionary of tool arguments, empty dict if not found.
        """
        target_tool = tool_name or self.tool_name

        if self.assistant_message.tool_calls:
            for tool_call in self.assistant_message.tool_calls:
                if tool_call.function.name == target_tool:
                    try:
                        return json.loads(tool_call.function.arguments)
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


class Turn(BaseModel):
    """
    Represents a complete turn in the test conversation.

    CORRECT TURN DEFINITION:
    A turn = One complete Penelope request → Target response cycle, which may include:
    - Multiple internal tool executions (analyze_response, extract_information, etc.)
    - One target interaction (send_message_to_target, invoke_api_endpoint, etc.)
    - Target's response

    This creates one user-assistant message pair in the conversation history.

    Example turn flow:
    1. LLM thinks → analyze_response (internal)
    2. LLM thinks → extract_information (internal)
    3. LLM thinks → send_message_to_target (target interaction) → Target responds

    All of the above is ONE turn, regardless of how many tools Penelope used.
    The turn is complete when a target interaction occurs and the target responds.
    """

    turn_number: int = Field(description="The turn number (1-indexed)")
    timestamp: datetime = Field(default_factory=datetime.now)

    # All tool executions within this turn (internal + target interaction)
    executions: List[ToolExecution] = Field(
        default_factory=list, description="All tool executions in this turn"
    )

    # The target interaction that completed this turn
    target_interaction: ToolExecution = Field(
        description="The target interaction that completed this turn"
    )

    # Turn-level metadata
    evaluation: Optional[str] = Field(
        default=None, description="Evaluation of progress after this turn"
    )

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime, _info):
        """Serialize datetime to ISO format string."""
        return timestamp.isoformat()


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

    CORRECT TURN DEFINITION:
    - A turn = One complete Penelope request → Target response cycle
    - A turn can contain multiple tool executions (internal + one target interaction)
    - A turn is complete when a target interaction occurs and target responds
    - current_turn: Number of completed turns (complete request-response cycles)
    - len(turns): Number of completed turns (same as current_turn)
    - len(conversation): Number of SDK conversation messages (same as current_turn)
    - current_turn_executions: Tool executions in the current (incomplete) turn
    """

    context: TestContext
    turns: List[Turn] = field(default_factory=list)  # Completed turns only

    # Native SDK conversation tracking - built incrementally as turns complete
    conversation: ConversationHistory = field(
        default_factory=lambda: ConversationHistory.from_messages([])
    )

    current_turn: int = 0  # Number of completed turns
    current_turn_executions: List[ToolExecution] = field(
        default_factory=list
    )  # Executions in current turn
    session_id: Optional[str] = None
    findings: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    # Store SDK metric evaluation results (supports multiple metrics)
    metric_results: List[Any] = field(default_factory=list)  # List of SDK MetricResults

    @property
    def all_executions(self) -> List[ToolExecution]:
        """Get all tool executions across all turns and current turn."""
        executions = []
        for turn in self.turns:
            executions.extend(turn.executions)
        executions.extend(self.current_turn_executions)
        return executions

    def add_execution(
        self,
        reasoning: str,
        assistant_message: AssistantMessage,
        tool_message: ToolMessage,
    ) -> Optional[Turn]:
        """
        Add a tool execution to the current turn.

        If this is a target interaction, it completes the turn and returns the Turn object.
        If this is an internal tool, it adds to current_turn_executions and returns None.

        Args:
            reasoning: Penelope's reasoning for this tool execution
            assistant_message: Assistant message with tool_calls
            tool_message: Tool response message

        Returns:
            Turn object if this execution completed a turn, None if it's an internal execution
        """
        # Extract tool name
        tool_name = ""
        if assistant_message.tool_calls and len(assistant_message.tool_calls) > 0:
            tool_name = assistant_message.tool_calls[0].function.name

        # Create tool execution
        execution = ToolExecution(
            tool_name=tool_name,
            reasoning=reasoning,
            assistant_message=assistant_message,
            tool_message=tool_message,
        )

        # Add to current turn executions
        self.current_turn_executions.append(execution)

        # Check if this completes a turn (target interaction)
        if self._is_target_interaction_tool(tool_name):
            # This completes the turn
            self.current_turn += 1

            turn = Turn(
                turn_number=self.current_turn,
                executions=self.current_turn_executions.copy(),  # All executions in this turn
                target_interaction=execution,  # The target interaction that completed the turn
            )

            # Add completed turn to turns list
            self.turns.append(turn)

            # Update SDK conversation
            self._update_conversation_from_turn(turn)

            # Clear current turn executions for next turn
            self.current_turn_executions.clear()

            return turn
        else:
            # Internal tool execution - turn not complete yet
            return None

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
        return ToolType.is_target_interaction(tool_name)

    def _update_conversation_from_turn(self, turn: Turn) -> None:
        """
        Update the conversation history from a completed turn.

        Creates a single conversation entry that represents the complete
        Penelope-target interaction as one turn.

        This ensures that SDK metrics see 1 conversation entry per Penelope turn,
        making turn counting consistent between Penelope and SDK evaluations.

        Args:
            turn: The completed turn to extract conversation from
        """
        from rhesis.penelope.schemas import UserMessage

        # Only process turns with target interactions
        if turn.target_interaction.tool_name == ToolType.SEND_MESSAGE_TO_TARGET:
            # Extract user message from target interaction
            target_args = turn.target_interaction.get_tool_call_arguments()
            user_msg = target_args.get("message", "")

            # Extract assistant response from target interaction result
            result = json.loads(turn.target_interaction.tool_message.content)
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
            for execution in turn.executions:
                messages.append(execution.assistant_message)
                messages.append(execution.tool_message)
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
        # Use the LAST goal evaluation result (final evaluation with complete conversation)
        goal_evaluation_flat = None
        if self.metric_results:
            # Find the last goal achievement metric result (should be the final evaluation)
            goal_results = [
                result
                for result in self.metric_results
                if result.details.get("is_goal_achievement_metric", False)
                or result.details.get("name") == "penelope_goal_evaluation"
            ]
            if goal_results:
                # Use the last (most recent) goal evaluation result
                goal_evaluation_flat = self._flatten_metric_result(goal_results[-1])
            else:
                # Fallback to first result for backward compatibility
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
            is_goal_metric = metric_dict.get("is_goal_achievement_metric", False)

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

        # Tool usage statistics (includes all executions: turns + internal tools)
        tool_calls = {}
        for execution in self.all_executions:
            tool_name = execution.tool_name
            if tool_name:
                if tool_name not in tool_calls:
                    tool_calls[tool_name] = {
                        "total_calls": 0,
                        "successful_calls": 0,
                        "failed_calls": 0,
                    }

                tool_calls[tool_name]["total_calls"] += 1

                # Check if tool call was successful by parsing tool_message content
                try:
                    tool_result = json.loads(execution.tool_message.content)
                    if tool_result.get("success", False):
                        tool_calls[tool_name]["successful_calls"] += 1
                    else:
                        tool_calls[tool_name]["failed_calls"] += 1
                except (json.JSONDecodeError, AttributeError):
                    # If we can't parse the result, count as failed
                    tool_calls[tool_name]["failed_calls"] += 1

        stats["tool_usage"] = tool_calls

        # Overall statistics
        stats["total_turns"] = len(self.turns)
        # Count successful target interactions (turns where target interaction succeeded)
        successful_interactions = 0
        for turn in self.turns:
            try:
                target_result = json.loads(turn.target_interaction.tool_message.content)
                if target_result.get("success", False):
                    successful_interactions += 1
            except (json.JSONDecodeError, AttributeError):
                # If we can't parse the result, count as failed
                pass

        stats["successful_interactions"] = successful_interactions

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

    def _extract_penelope_message_from_interaction(
        self, target_interaction: ToolExecution
    ) -> tuple[str, Optional[str]]:
        """
        Extract Penelope's message and session ID from a target interaction.

        Handles different target interaction tool types and provides appropriate
        message extraction for conversation summaries.

        Args:
            target_interaction: The ToolExecution representing the target interaction

        Returns:
            Tuple of (penelope_message, session_id)
        """
        tool_args = target_interaction.get_tool_call_arguments()

        if target_interaction.tool_name == ToolType.SEND_MESSAGE_TO_TARGET:
            penelope_message = tool_args.get("message", "")
            session_id = tool_args.get("session_id")
            return penelope_message, session_id

        elif target_interaction.tool_name == ToolType.INVOKE_API_ENDPOINT:
            # For API endpoints, use the request data or a summary
            penelope_message = tool_args.get("data", str(tool_args)) if tool_args else "API call"
            return penelope_message, None

        elif target_interaction.tool_name == ToolType.SEND_WEBHOOK:
            # For webhooks, use the payload or a summary
            penelope_message = (
                tool_args.get("payload", str(tool_args)) if tool_args else "Webhook call"
            )
            return penelope_message, None

        else:
            # Fallback for unknown target interaction types
            penelope_message = (
                f"{target_interaction.tool_name}: {str(tool_args)}"
                if tool_args
                else "Unknown interaction"
            )
            return penelope_message, None

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
            # Use the target interaction from the turn (which completed the turn)
            target_interaction = turn.target_interaction

            # Only include target interaction turns in the conversation summary
            if not self._is_target_interaction_tool(target_interaction.tool_name):
                continue

            # Extract Penelope's message from the target interaction
            penelope_message, session_id = self._extract_penelope_message_from_interaction(
                target_interaction
            )

            # Extract target response from target interaction tool message
            target_response = ""
            success = False

            try:
                tool_content = json.loads(target_interaction.tool_message.content)
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

            # Create conversation turn (use turn number for display consistency)
            conversation_turn = ConversationTurn(
                turn=turn.turn_number,  # Actual turn number (target interactions only)
                timestamp=turn.timestamp.isoformat(),
                penelope_reasoning=target_interaction.reasoning,  # Use target interaction reasoning
                penelope_message=penelope_message,
                target_response=target_response,
                session_id=session_id,
                success=success,
            )

            summary.append(conversation_turn)

        return summary
