"""Tests for Penelope context and state management."""

from datetime import datetime

from rhesis.penelope.context import (
    ExecutionStatus,
    TestContext,
    TestResult,
    TestState,
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
    """Test adding a turn to TestState."""
    assistant_msg = AssistantMessage(
        content="Test reasoning",
        tool_calls=[
            MessageToolCall(
                id="call_1",
                type="function",
                function=FunctionCall(name="test_tool", arguments='{"param": "value"}'),
            )
        ],
    )

    tool_msg = ToolMessage(
        tool_call_id="call_1",
        name="test_tool",
        content='{"success": true, "output": {"result": "test"}}',
    )

    sample_test_state.add_turn(
        reasoning="Test reasoning",
        assistant_message=assistant_msg,
        tool_message=tool_msg,
    )

    assert sample_test_state.current_turn == 1
    assert len(sample_test_state.turns) == 1

    turn = sample_test_state.turns[0]
    assert turn.turn_number == 1
    assert turn.reasoning == "Test reasoning"
    assert turn.tool_name == "test_tool"


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
                function=FunctionCall(name="test_tool", arguments="{}"),
            )
        ],
    )

    tool_msg = ToolMessage(tool_call_id="call_1", name="test_tool", content='{"success": true}')

    sample_test_state.add_turn(
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
                function=FunctionCall(name="test_tool", arguments='{"param": "value"}'),
            )
        ],
    )

    tool_msg = ToolMessage(
        tool_call_id="call_1",
        name="test_tool",
        content='{"success": true, "output": {"result": "test"}}',
    )

    turn = Turn(
        turn_number=1,
        assistant_message=assistant_msg,
        tool_message=tool_msg,
        reasoning="Test reasoning",
    )

    # Test property accessors
    assert turn.tool_name == "test_tool"
    assert turn.tool_arguments == {"param": "value"}

    tool_result = turn.tool_result
    assert tool_result["success"] is True
    assert tool_result["output"]["result"] == "test"


def test_turn_properties_with_no_tool_calls():
    """Test Turn properties when no tool_calls are present."""
    assistant_msg = AssistantMessage(content="Test reasoning", tool_calls=None)

    tool_msg = ToolMessage(tool_call_id="call_1", name="test_tool", content='{"success": true}')

    turn = Turn(
        turn_number=1,
        assistant_message=assistant_msg,
        tool_message=tool_msg,
        reasoning="Test reasoning",
    )

    # Should handle missing tool_calls gracefully
    assert turn.tool_name == "unknown"
    assert turn.tool_arguments == {}


def test_test_result_creation():
    """Test TestResult initialization."""
    turn = Turn(
        turn_number=1,
        assistant_message=AssistantMessage(
            content="Test",
            tool_calls=[
                MessageToolCall(
                    id="call_1",
                    type="function",
                    function=FunctionCall(name="test_tool", arguments="{}"),
                )
            ],
        ),
        tool_message=ToolMessage(
            tool_call_id="call_1", name="test_tool", content='{"success": true}'
        ),
        reasoning="Test",
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
