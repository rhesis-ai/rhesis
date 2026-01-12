"""Tests for base Target class."""

import pytest

from rhesis.penelope.targets.base import Target, TargetResponse


def test_target_response_creation():
    """Test TargetResponse initialization."""
    response = TargetResponse(
        success=True,
        content="Test response",
        conversation_id="conv-123",
        metadata={"key": "value"},
        error=None,
    )

    assert response.success is True
    assert response.content == "Test response"
    assert response.conversation_id == "conv-123"
    assert response.metadata == {"key": "value"}
    assert response.error is None


def test_target_response_defaults():
    """Test TargetResponse default values."""
    response = TargetResponse(success=True, content="Test")

    assert response.conversation_id is None
    assert response.metadata == {}
    assert response.error is None


def test_target_response_with_error():
    """Test TargetResponse with error."""
    response = TargetResponse(
        success=False,
        content="",
        error="Connection failed",
    )

    assert response.success is False
    assert response.error == "Connection failed"


def test_target_cannot_be_instantiated():
    """Test that Target cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Target()


def test_target_abstract_properties():
    """Test that Target has expected abstract properties."""
    assert hasattr(Target, "target_type")
    assert hasattr(Target, "target_id")
    assert hasattr(Target, "description")

    # Check that they are abstract
    assert Target.target_type.__isabstractmethod__
    assert Target.target_id.__isabstractmethod__
    assert Target.description.__isabstractmethod__


def test_target_abstract_methods():
    """Test that Target has expected abstract methods."""
    assert hasattr(Target, "send_message")
    assert hasattr(Target, "validate_configuration")

    # Check that they are abstract
    assert Target.send_message.__isabstractmethod__
    assert Target.validate_configuration.__isabstractmethod__


def test_target_concrete_methods():
    """Test Target concrete method (get_tool_documentation)."""

    class TestTarget(Target):
        @property
        def target_type(self) -> str:
            return "test"

        @property
        def target_id(self) -> str:
            return "test-123"

        @property
        def description(self) -> str:
            return "Test target"

        def send_message(self, message: str, conversation_id=None, **kwargs):
            return TargetResponse(
                success=True, content="Test response", conversation_id=conversation_id
            )

        def validate_configuration(self):
            return True, None

    target = TestTarget()

    # Test concrete method
    doc = target.get_tool_documentation()
    assert "Target Type: test" in doc
    assert "Target ID: test-123" in doc
    assert "Description: Test target" in doc


def test_target_implementation(mock_target):
    """Test that mock_target fixture works correctly."""
    assert mock_target.target_type == "mock"
    assert mock_target.target_id == "mock-target-123"
    assert mock_target.description == "Mock target for testing"

    response = mock_target.send_message("Hello")
    assert response.success is True
    assert response.content == "Mock response"

    is_valid, error = mock_target.validate_configuration()
    assert is_valid is True
    assert error is None


def test_target_send_message_with_session(mock_target):
    """Test send_message with conversation_id."""
    response = mock_target.send_message("Hello", conversation_id="conv-456")

    assert response.success is True
    assert response.conversation_id == "conv-456"


def test_target_send_message_with_kwargs(mock_target):
    """Test send_message accepts additional kwargs."""
    # Should not raise an error
    response = mock_target.send_message("Hello", conversation_id="conv-123", extra_param="value")

    assert response.success is True
