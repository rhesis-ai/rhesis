"""Tests for Penelope context and state management."""

from datetime import datetime

from rhesis.penelope.context import (
    ExecutionStatus,
    TestContext,
    TestResult,
    TestState,
    ToolExecution,
    Turn,
)
from rhesis.penelope.schemas import (
    AssistantMessage,
    FunctionCall,
    MessageToolCall,
    ToolMessage,
)


def test_test_context_creation():
    """Test TestContext initialization."""
    context = TestContext(
        target_id="target-123",
        target_type="endpoint",
        instructions="Test instructions",
        goal="Test goal",
        scenario="Test scenario",
        context={"key": "value"},
        max_turns=10,
    )

    assert context.target_id == "target-123"
    assert context.target_type == "endpoint"
    assert context.instructions == "Test instructions"
    assert context.goal == "Test goal"
    assert context.scenario == "Test scenario"
    assert context.context == {"key": "value"}
    assert context.max_turns == 10


def test_test_context_optional_fields():
    """Test TestContext with optional fields."""
    context = TestContext(
        target_id="target-123",
        target_type="endpoint",
        instructions="Test instructions",
        goal="Test goal",
    )

    assert context.scenario is None
    assert context.restrictions is None
    assert context.context == {}
    assert context.max_turns == 20  # Default value


def test_test_state_initialization(sample_test_context):
    """Test TestState initialization."""
    state = TestState(context=sample_test_context)

    assert state.context == sample_test_context
    assert state.current_turn == 0
    assert len(state.turns) == 0
    assert len(state.findings) == 0
    assert isinstance(state.start_time, datetime)


def test_test_state_add_turn(sample_test_state):
    """Test adding a turn to TestState using add_execution."""
    # Use a target interaction tool to complete a turn
    assistant_msg = AssistantMessage(
        content="Test reasoning",
        tool_calls=[
            MessageToolCall(
                id="call_1",
                type="function",
                function=FunctionCall(
                    name="send_message_to_target", arguments='{"param": "value"}'
                ),
            )
        ],
    )

    tool_msg = ToolMessage(
        tool_call_id="call_1",
        name="send_message_to_target",
        content='{"success": true, "output": {"result": "test"}}',
    )

    completed_turn = sample_test_state.add_execution(
        reasoning="Test reasoning",
        assistant_message=assistant_msg,
        tool_message=tool_msg,
    )

    # Verify turn was completed
    assert completed_turn is not None
    assert sample_test_state.current_turn == 1
    assert len(sample_test_state.turns) == 1

    turn = sample_test_state.turns[0]
    assert turn.turn_number == 1
    assert turn.target_interaction.reasoning == "Test reasoning"
    assert turn.target_interaction.tool_name == "send_message_to_target"


def test_test_state_add_finding(sample_test_state):
    """Test adding findings to TestState."""
    sample_test_state.add_finding("Finding 1")
    sample_test_state.add_finding("Finding 2")

    assert len(sample_test_state.findings) == 2
    assert "Finding 1" in sample_test_state.findings
    assert "Finding 2" in sample_test_state.findings


def test_test_state_get_conversation_messages(sample_test_state):
    """Test getting conversation messages from TestState."""
    # Add a turn
    assistant_msg = AssistantMessage(
        content="Test reasoning",
        tool_calls=[
            MessageToolCall(
                id="call_1",
                type="function",
                function=FunctionCall(name="send_message_to_target", arguments='{"message": "Hello"}'),
            )
        ],
    )

    tool_msg = ToolMessage(tool_call_id="call_1", name="send_message_to_target", content='{"success": true}')

    sample_test_state.add_execution(
        reasoning="Test reasoning",
        assistant_message=assistant_msg,
        tool_message=tool_msg,
    )

    messages = sample_test_state.get_conversation_messages()

    assert len(messages) == 2
    assert messages[0].role == "assistant"
    assert messages[1].role == "tool"


def test_test_state_to_result(sample_test_state):
    """Test converting TestState to TestResult."""
    sample_test_state.add_finding("Finding 1")

    result = sample_test_state.to_result(ExecutionStatus.SUCCESS, goal_achieved=True)

    assert isinstance(result, TestResult)
    assert result.status == ExecutionStatus.SUCCESS
    assert result.goal_achieved is True
    assert result.turns_used == 0
    # Findings now include summary information (status + turn count) plus findings
    assert len(result.findings) == 3
    assert "Finding 1" in result.findings
    assert any("Test success" in f for f in result.findings)
    assert any("Completed in 0 turn" in f for f in result.findings)


def test_turn_properties():
    """Test Turn property accessors."""
    assistant_msg = AssistantMessage(
        content="Test reasoning",
        tool_calls=[
            MessageToolCall(
                id="call_1",
                type="function",
                function=FunctionCall(name="send_message_to_target", arguments='{"param": "value"}'),
            )
        ],
    )

    tool_msg = ToolMessage(
        tool_call_id="call_1",
        name="send_message_to_target",
        content='{"success": true, "output": {"result": "test"}}',
    )

    # Create a ToolExecution for the target interaction
    target_execution = ToolExecution(
        tool_name="send_message_to_target",
        reasoning="Test reasoning",
        assistant_message=assistant_msg,
        tool_message=tool_msg,
    )

    turn = Turn(
        turn_number=1,
        executions=[target_execution],
        target_interaction=target_execution,
    )

    # Test property accessors
    assert turn.target_interaction.tool_name == "send_message_to_target"
    assert turn.target_interaction.get_tool_call_arguments() == {"param": "value"}

    tool_result = turn.target_interaction.tool_result
    assert tool_result["success"] is True
    assert tool_result["output"]["result"] == "test"


def test_turn_properties_with_no_tool_calls():
    """Test Turn properties when no tool_calls are present."""
    assistant_msg = AssistantMessage(content="Test reasoning", tool_calls=None)

    tool_msg = ToolMessage(tool_call_id="call_1", name="send_message_to_target", content='{"success": true}')

    # Create a ToolExecution for the target interaction
    target_execution = ToolExecution(
        tool_name="send_message_to_target",
        reasoning="Test reasoning",
        assistant_message=assistant_msg,
        tool_message=tool_msg,
    )

    turn = Turn(
        turn_number=1,
        executions=[target_execution],
        target_interaction=target_execution,
    )

    # Should handle missing tool_calls gracefully
    assert turn.target_interaction.tool_name == "send_message_to_target"
    assert turn.target_interaction.get_tool_call_arguments() == {}


def test_test_result_creation():
    """Test TestResult initialization."""
    assistant_msg = AssistantMessage(
            content="Test",
            tool_calls=[
                MessageToolCall(
                    id="call_1",
                    type="function",
                function=FunctionCall(name="send_message_to_target", arguments="{}"),
                )
            ],
    )
    
    tool_msg = ToolMessage(
        tool_call_id="call_1", name="send_message_to_target", content='{"success": true}'
    )
    
    # Create a ToolExecution for the target interaction
    target_execution = ToolExecution(
        tool_name="send_message_to_target",
        reasoning="Test",
        assistant_message=assistant_msg,
        tool_message=tool_msg,
    )
    
    turn = Turn(
        turn_number=1,
        executions=[target_execution],
        target_interaction=target_execution,
    )

    result = TestResult(
        status=ExecutionStatus.SUCCESS,
        goal_achieved=True,
        turns_used=1,
        findings=["Finding 1"],
        history=[turn],
        metadata={"test": "value"},
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert result.goal_achieved is True
    assert result.turns_used == 1
    assert len(result.findings) == 1
    assert len(result.history) == 1
    assert result.metadata == {"test": "value"}


def test_execution_status_enum_values():
    """Test ExecutionStatus enum values."""
    assert ExecutionStatus.IN_PROGRESS == "in_progress"
    assert ExecutionStatus.SUCCESS == "success"
    assert ExecutionStatus.FAILURE == "failure"
    assert ExecutionStatus.ERROR == "error"
    assert ExecutionStatus.TIMEOUT == "timeout"
    assert ExecutionStatus.MAX_ITERATIONS == "max_iterations"


def test_test_context_with_restrictions():
    """Test TestContext with restrictions field."""
    context = TestContext(
        target_id="target-123",
        target_type="endpoint",
        instructions="Test instructions",
        goal="Test goal",
        restrictions="Do not use profanity\nAvoid offensive content",
    )

    assert context.restrictions == "Do not use profanity\nAvoid offensive content"


def test_test_context_restrictions_optional():
    """Test that restrictions field is optional."""
    context = TestContext(
        target_id="target-123",
        target_type="endpoint",
        instructions="Test instructions",
        goal="Test goal",
        scenario="Test scenario",
    )

    assert context.restrictions is None


def test_test_context_full_initialization():
    """Test TestContext with all fields including restrictions."""
    context = TestContext(
        target_id="target-123",
        target_type="endpoint",
        instructions="Test instructions",
        goal="Test goal",
        scenario="Test scenario",
        restrictions="Do not test payment features\nStay within rate limits",
        context={"key": "value"},
        max_turns=15,
        timeout_seconds=300.0,
    )

    assert context.target_id == "target-123"
    assert context.target_type == "endpoint"
    assert context.instructions == "Test instructions"
    assert context.goal == "Test goal"
    assert context.scenario == "Test scenario"
    assert context.restrictions == "Do not test payment features\nStay within rate limits"
    assert context.context == {"key": "value"}
    assert context.max_turns == 15
    assert context.timeout_seconds == 300.0


# Tests for _generate_metrics method with multiple metrics support


def test_generate_metrics_with_no_metrics():
    """Test _generate_metrics returns empty dict when no metrics available."""
    test_context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test",
        goal="Test goal",
    )
    state = TestState(context=test_context)

    # No metrics in state
    metrics = state._generate_metrics(goal_achieved=True)

    # Should return empty dict - no fallbacks
    assert metrics == {}
    assert len(metrics) == 0


def test_generate_metrics_with_single_metric():
    """Test _generate_metrics with single MetricResult."""
    from rhesis.sdk.metrics.base import MetricResult

    test_context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test",
        goal="Test goal",
    )
    state = TestState(context=test_context)

    # Add single metric result
    metric_result = MetricResult(
        score=0.85,
        details={
            "is_successful": True,
            "reason": "Goal achieved",
            "name": "test_metric",
        },
    )
    state.metric_results = [metric_result]

    metrics = state._generate_metrics(goal_achieved=True)

    # Verify metric was included with flattened structure
    assert "Test Metric" in metrics  # snake_case to Title Case
    assert metrics["Test Metric"]["score"] == 0.85
    assert metrics["Test Metric"]["is_successful"] is True  # Flattened from details
    assert metrics["Test Metric"]["reason"] == "Goal achieved"  # Flattened from details


def test_generate_metrics_with_multiple_metrics():
    """Test _generate_metrics with multiple MetricResults."""
    from rhesis.sdk.metrics.base import MetricResult

    test_context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test",
        goal="Test goal",
    )
    state = TestState(context=test_context)

    # Add multiple metric results
    metric1 = MetricResult(score=0.9, details={"name": "goal_achievement", "is_successful": True})
    metric2 = MetricResult(score=0.75, details={"name": "turn_relevancy"})
    metric3 = MetricResult(score=0.85, details={"name": "custom_metric"})

    state.metric_results = [metric1, metric2, metric3]

    metrics = state._generate_metrics(goal_achieved=True)

    # Verify all metrics were included
    assert len(metrics) == 3
    assert "Goal Achievement" in metrics
    assert "Turn Relevancy" in metrics
    assert "Custom Metric" in metrics

    # Verify scores
    assert metrics["Goal Achievement"]["score"] == 0.9
    assert metrics["Turn Relevancy"]["score"] == 0.75
    assert metrics["Custom Metric"]["score"] == 0.85


def test_generate_metrics_with_criteria_evaluations():
    """Test _generate_metrics includes criteria counts for goal achievement."""
    from rhesis.sdk.metrics.base import MetricResult

    test_context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test",
        goal="Test goal",
    )
    state = TestState(context=test_context)

    # Add metric with criteria evaluations
    metric_result = MetricResult(
        score=0.8,
        details={
            "name": "goal_achievement",
            "is_successful": True,
            "criteria_evaluations": [
                {"criterion": "C1", "met": True, "evidence": "E1", "relevant_turns": [1]},
                {"criterion": "C2", "met": False, "evidence": "E2", "relevant_turns": [2]},
                {"criterion": "C3", "met": True, "evidence": "E3", "relevant_turns": [1, 2]},
            ],
            "all_criteria_met": False,
            "confidence": 0.85,
        },
    )
    state.metric_results = [metric_result]

    metrics = state._generate_metrics(goal_achieved=True)

    # Verify criteria counts were added
    goal_metric = metrics["Goal Achievement"]
    assert goal_metric["criteria_met"] == 2
    assert goal_metric["criteria_total"] == 3
    assert goal_metric["score"] == 0.8


def test_generate_metrics_without_criteria():
    """Test _generate_metrics handles metrics without criteria gracefully."""
    from rhesis.sdk.metrics.base import MetricResult

    test_context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test",
        goal="Test goal",
    )
    state = TestState(context=test_context)

    # Add metric without criteria_evaluations
    metric_result = MetricResult(score=0.9, details={"name": "simple_metric"})
    state.metric_results = [metric_result]

    metrics = state._generate_metrics(goal_achieved=True)

    # Verify metric is included without criteria counts
    assert "Simple Metric" in metrics
    assert "criteria_met" not in metrics["Simple Metric"]
    assert "criteria_total" not in metrics["Simple Metric"]


def test_generate_metrics_dynamic_naming():
    """Test _generate_metrics uses dynamic naming from metric details."""
    from rhesis.sdk.metrics.base import MetricResult

    test_context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test",
        goal="Test goal",
    )
    state = TestState(context=test_context)

    # Metrics with different name formats
    metric1 = MetricResult(score=0.9, details={"name": "my_custom_metric"})
    metric2 = MetricResult(score=0.8, details={"name": "another_test"})
    metric3 = MetricResult(score=0.7, details={})  # No name

    state.metric_results = [metric1, metric2, metric3]

    metrics = state._generate_metrics(goal_achieved=True)

    # Verify Title Case conversion
    assert "My Custom Metric" in metrics
    assert "Another Test" in metrics
    assert "Penelope Goal Evaluation" in metrics  # Fallback for missing name


def test_generate_metrics_serialization():
    """Test _generate_metrics flattens MetricResult details to top level."""
    from rhesis.sdk.metrics.base import MetricResult

    test_context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test",
        goal="Test goal",
    )
    state = TestState(context=test_context)

    # Add metric with complex details
    metric_result = MetricResult(
        score=0.95,
        details={
            "name": "complex_metric",
            "is_successful": True,
            "reason": "All checks passed",
            "metadata": {"key1": "value1", "key2": [1, 2, 3]},
        },
    )
    state.metric_results = [metric_result]

    metrics = state._generate_metrics(goal_achieved=True)

    # Verify flattened structure - all details fields are at top level
    complex_metric = metrics["Complex Metric"]
    assert complex_metric["score"] == 0.95
    assert complex_metric["is_successful"] is True  # Flattened from details
    assert complex_metric["reason"] == "All checks passed"  # Flattened from details
    assert complex_metric["metadata"]["key1"] == "value1"  # Nested object preserved
    assert complex_metric["metadata"]["key2"] == [1, 2, 3]
    assert complex_metric["name"] == "complex_metric"  # Also flattened
    # No nested 'details' key
    assert "details" not in complex_metric or complex_metric["score"] == 0.95
