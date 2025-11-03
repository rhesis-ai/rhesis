"""Tests for TargetInteractionTool."""

import pytest
from unittest.mock import Mock
from rhesis.penelope.tools.target_interaction import TargetInteractionTool
from rhesis.penelope.tools.base import ToolResult
from rhesis.penelope.targets.base import TargetResponse


def test_target_interaction_tool_initialization(mock_target):
    """Test TargetInteractionTool initialization."""
    tool = TargetInteractionTool(mock_target)

    assert tool.target == mock_target
    assert tool.name == "send_message_to_target"


def test_target_interaction_tool_properties(mock_target):
    """Test TargetInteractionTool properties."""
    tool = TargetInteractionTool(mock_target)

    assert tool.name == "send_message_to_target"
    assert "send" in tool.description.lower()
    assert "message" in tool.description.lower()


def test_target_interaction_tool_description_includes_target_doc(mock_target):
    """Test that tool description includes target documentation."""
    tool = TargetInteractionTool(mock_target)

    description = tool.description
    # Should include target's tool documentation
    assert "Mock target" in description or "mock" in description.lower()


def test_target_interaction_tool_execute_basic(mock_target):
    """Test TargetInteractionTool basic execution."""
    tool = TargetInteractionTool(mock_target)

    result = tool.execute(message="Hello")

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "response" in result.output
    assert "session_id" in result.output
    assert result.output["response"] == "Mock response"


def test_target_interaction_tool_execute_with_session(mock_target):
    """Test TargetInteractionTool execution with session_id."""
    tool = TargetInteractionTool(mock_target)

    result = tool.execute(message="Hello", session_id="session-123")

    assert result.success is True
    assert result.output["session_id"] == "session-123"


def test_target_interaction_tool_includes_metadata(mock_target):
    """Test TargetInteractionTool includes metadata in result."""
    tool = TargetInteractionTool(mock_target)

    result = tool.execute(message="Test message", session_id="session-456")

    assert result.success is True
    assert "message_sent" in result.metadata
    assert result.metadata["message_sent"] == "Test message"
    assert result.metadata["session_id_used"] == "session-456"
    assert result.metadata["target_type"] == "mock"
    assert result.metadata["target_id"] == "mock-target-123"


def test_target_interaction_tool_target_returns_error(mock_target):
    """Test TargetInteractionTool when target returns error."""
    tool = TargetInteractionTool(mock_target)

    # Make mock_target return an error
    mock_target.send_message = Mock(
        return_value=TargetResponse(
            success=False,
            content="",
            error="Connection failed",
        )
    )

    result = tool.execute(message="Hello")

    assert result.success is False
    assert "Connection failed" in result.error


def test_target_interaction_tool_target_raises_exception(mock_target):
    """Test TargetInteractionTool handles exceptions from target."""
    tool = TargetInteractionTool(mock_target)

    # Make mock_target raise an exception
    mock_target.send_message = Mock(side_effect=RuntimeError("Unexpected error"))

    result = tool.execute(message="Hello")

    assert result.success is False
    assert "Unexpected error" in result.error


def test_target_interaction_tool_preserves_target_metadata(mock_target):
    """Test TargetInteractionTool preserves metadata from target response."""
    tool = TargetInteractionTool(mock_target)

    # Make mock_target return response with metadata
    mock_target.send_message = Mock(
        return_value=TargetResponse(
            success=True,
            content="Response with metadata",
            session_id="session-789",
            metadata={"key": "value", "custom": "data"},
        )
    )

    result = tool.execute(message="Hello")

    assert result.success is True
    assert "metadata" in result.output
    assert result.output["metadata"]["key"] == "value"
    assert result.output["metadata"]["custom"] == "data"


def test_target_interaction_tool_handles_none_session():
    """Test TargetInteractionTool handles None session_id correctly."""

    class TestTarget:
        @property
        def target_type(self):
            return "test"

        @property
        def target_id(self):
            return "test-123"

        def send_message(self, message, session_id=None, **kwargs):
            # Return session_id as None if not provided
            return TargetResponse(
                success=True,
                content="Response",
                session_id=session_id,
            )

        def get_tool_documentation(self):
            return "Test target"

    target = TestTarget()
    tool = TargetInteractionTool(target)

    result = tool.execute(message="Hello")

    assert result.success is True
    assert result.output["session_id"] is None


def test_target_interaction_tool_passes_kwargs(mock_target):
    """Test TargetInteractionTool passes additional kwargs to target."""
    tool = TargetInteractionTool(mock_target)

    # Create a mock that captures all arguments
    original_send = mock_target.send_message
    mock_target.send_message = Mock(side_effect=original_send)

    result = tool.execute(
        message="Hello",
        session_id="session-123",
        extra_param="extra_value",
    )

    # Verify send_message was called with kwargs
    mock_target.send_message.assert_called_once()
    call_kwargs = mock_target.send_message.call_args.kwargs
    assert "extra_param" in call_kwargs
    assert call_kwargs["extra_param"] == "extra_value"

