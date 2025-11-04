"""Tests for Penelope Pydantic schemas."""

import pytest
from pydantic import ValidationError
from rhesis.penelope.schemas import (
    FunctionCall,
    MessageToolCall,
    AssistantMessage,
    ToolMessage,
    SendMessageParams,
    AnalyzeResponseParams,
    ExtractInformationParams,
    CriterionEvaluation,
    SimpleGoalEval,
    ToolCall,
)


def test_function_call_creation():
    """Test FunctionCall schema."""
    func_call = FunctionCall(name="test_function", arguments='{"param": "value"}')

    assert func_call.name == "test_function"
    assert func_call.arguments == '{"param": "value"}'


def test_function_call_validation():
    """Test FunctionCall requires all fields."""
    with pytest.raises(ValidationError):
        FunctionCall(name="test_function")  # Missing arguments


def test_message_tool_call_creation():
    """Test MessageToolCall schema."""
    func_call = FunctionCall(name="test_function", arguments="{}")
    tool_call = MessageToolCall(
        id="call_123", type="function", function=func_call
    )

    assert tool_call.id == "call_123"
    assert tool_call.type == "function"
    assert tool_call.function.name == "test_function"


def test_message_tool_call_default_type():
    """Test MessageToolCall has default type."""
    func_call = FunctionCall(name="test_function", arguments="{}")
    tool_call = MessageToolCall(id="call_123", function=func_call)

    assert tool_call.type == "function"


def test_assistant_message_creation():
    """Test AssistantMessage schema."""
    func_call = FunctionCall(name="test_function", arguments="{}")
    tool_call = MessageToolCall(id="call_123", function=func_call)

    message = AssistantMessage(content="Test content", tool_calls=[tool_call])

    assert message.role == "assistant"
    assert message.content == "Test content"
    assert len(message.tool_calls) == 1
    assert message.tool_calls[0].id == "call_123"


def test_assistant_message_optional_fields():
    """Test AssistantMessage with optional fields."""
    message = AssistantMessage()

    assert message.role == "assistant"
    assert message.content is None
    assert message.tool_calls is None


def test_assistant_message_extra_fields():
    """Test AssistantMessage allows extra fields."""
    message = AssistantMessage(content="Test", custom_field="custom_value")

    assert message.content == "Test"
    # Extra fields should be allowed but not validated


def test_tool_message_creation():
    """Test ToolMessage schema."""
    message = ToolMessage(
        tool_call_id="call_123",
        name="test_tool",
        content='{"success": true}',
    )

    assert message.role == "tool"
    assert message.tool_call_id == "call_123"
    assert message.name == "test_tool"
    assert message.content == '{"success": true}'


def test_tool_message_validation():
    """Test ToolMessage requires all fields."""
    with pytest.raises(ValidationError):
        ToolMessage(tool_call_id="call_123")  # Missing name and content


def test_send_message_params():
    """Test SendMessageParams schema."""
    params = SendMessageParams(message="Hello", session_id="session-123")

    assert params.message == "Hello"
    assert params.session_id == "session-123"


def test_send_message_params_optional_session():
    """Test SendMessageParams with optional session_id."""
    params = SendMessageParams(message="Hello")

    assert params.message == "Hello"
    assert params.session_id is None


def test_analyze_response_params():
    """Test AnalyzeResponseParams schema."""
    params = AnalyzeResponseParams(
        response_text="Response", analysis_focus="tone", context="Context"
    )

    assert params.response_text == "Response"
    assert params.analysis_focus == "tone"
    assert params.context == "Context"


def test_analyze_response_params_optional_context():
    """Test AnalyzeResponseParams with optional context."""
    params = AnalyzeResponseParams(
        response_text="Response", analysis_focus="tone"
    )

    assert params.context is None


def test_extract_information_params():
    """Test ExtractInformationParams schema."""
    params = ExtractInformationParams(
        response_text="Response", extraction_target="email"
    )

    assert params.response_text == "Response"
    assert params.extraction_target == "email"


def test_criterion_evaluation():
    """Test CriterionEvaluation schema."""
    criterion = CriterionEvaluation(
        criterion="Chatbot provides accurate info",
        met=True,
        evidence="The chatbot stated correct facts",
    )

    assert criterion.criterion == "Chatbot provides accurate info"
    assert criterion.met is True
    assert criterion.evidence == "The chatbot stated correct facts"


def test_simple_goal_eval():
    """Test SimpleGoalEval schema."""
    criteria = [
        CriterionEvaluation(
            criterion="Criterion 1", met=True, evidence="Evidence 1"
        ),
        CriterionEvaluation(
            criterion="Criterion 2", met=True, evidence="Evidence 2"
        ),
    ]

    goal_eval = SimpleGoalEval(
        turn_count=3,
        criteria_evaluations=criteria,
        all_criteria_met=True,
        goal_achieved=True,
        confidence=0.9,
        reasoning="All criteria were met successfully",
        evidence=["Quote 1", "Quote 2"],
    )

    assert goal_eval.turn_count == 3
    assert len(goal_eval.criteria_evaluations) == 2
    assert goal_eval.all_criteria_met is True
    assert goal_eval.goal_achieved is True
    assert goal_eval.confidence == 0.9


def test_simple_goal_eval_confidence_validation():
    """Test SimpleGoalEval confidence must be between 0 and 1."""
    criteria = [
        CriterionEvaluation(
            criterion="Test", met=True, evidence="Evidence"
        )
    ]

    # Valid confidence
    goal_eval = SimpleGoalEval(
        turn_count=1,
        criteria_evaluations=criteria,
        all_criteria_met=True,
        goal_achieved=True,
        confidence=0.5,
        reasoning="Test",
    )
    assert goal_eval.confidence == 0.5

    # Invalid confidence (too high)
    with pytest.raises(ValidationError):
        SimpleGoalEval(
            turn_count=1,
            criteria_evaluations=criteria,
            all_criteria_met=True,
            goal_achieved=True,
            confidence=1.5,
            reasoning="Test",
        )

    # Invalid confidence (too low)
    with pytest.raises(ValidationError):
        SimpleGoalEval(
            turn_count=1,
            criteria_evaluations=criteria,
            all_criteria_met=True,
            goal_achieved=True,
            confidence=-0.1,
            reasoning="Test",
        )


def test_simple_goal_eval_default_evidence():
    """Test SimpleGoalEval evidence defaults to empty list."""
    criteria = [
        CriterionEvaluation(
            criterion="Test", met=True, evidence="Evidence"
        )
    ]

    goal_eval = SimpleGoalEval(
        turn_count=1,
        criteria_evaluations=criteria,
        all_criteria_met=True,
        goal_achieved=True,
        confidence=0.9,
        reasoning="Test",
    )

    assert goal_eval.evidence == []


def test_tool_call_with_send_message():
    """Test ToolCall with SendMessageParams."""
    tool_call = ToolCall(
        reasoning="Testing send message",
        tool_name="send_message_to_target",
        parameters=SendMessageParams(message="Hello", session_id="session-123"),
    )

    assert tool_call.reasoning == "Testing send message"
    assert tool_call.tool_name == "send_message_to_target"
    assert isinstance(tool_call.parameters, SendMessageParams)
    assert tool_call.parameters.message == "Hello"


def test_tool_call_with_analyze_response():
    """Test ToolCall with AnalyzeResponseParams."""
    tool_call = ToolCall(
        reasoning="Analyzing response",
        tool_name="analyze_response",
        parameters=AnalyzeResponseParams(
            response_text="Response", analysis_focus="tone"
        ),
    )

    assert tool_call.tool_name == "analyze_response"
    assert isinstance(tool_call.parameters, AnalyzeResponseParams)
    assert tool_call.parameters.response_text == "Response"


def test_tool_call_with_extract_information():
    """Test ToolCall with ExtractInformationParams."""
    tool_call = ToolCall(
        reasoning="Extracting info",
        tool_name="extract_information",
        parameters=ExtractInformationParams(
            response_text="Response", extraction_target="email"
        ),
    )

    assert tool_call.tool_name == "extract_information"
    assert isinstance(tool_call.parameters, ExtractInformationParams)
    assert tool_call.parameters.extraction_target == "email"


def test_tool_call_validation():
    """Test ToolCall requires all fields."""
    with pytest.raises(ValidationError):
        ToolCall(reasoning="Test")  # Missing tool_name and parameters

