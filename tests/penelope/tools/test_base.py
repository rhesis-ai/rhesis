"""Tests for base Tool class."""

import pytest

from rhesis.penelope.tools.base import Tool, ToolResult


def test_tool_result_creation():
    """Test ToolResult initialization."""
    result = ToolResult(
        success=True,
        output={"key": "value"},
        error=None,
        metadata={"meta": "data"},
    )

    assert result.success is True
    assert result.output == {"key": "value"}
    assert result.error is None
    assert result.metadata == {"meta": "data"}


def test_tool_result_defaults():
    """Test ToolResult default values."""
    result = ToolResult(success=True, output={"result": "test"})

    assert result.error is None
    assert result.metadata == {}


def test_tool_result_with_error():
    """Test ToolResult with error."""
    result = ToolResult(success=False, output={}, error="Something went wrong")

    assert result.success is False
    assert result.error == "Something went wrong"


def test_tool_cannot_be_instantiated():
    """Test that Tool cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Tool()


def test_tool_abstract_properties():
    """Test that Tool has expected abstract properties."""
    assert hasattr(Tool, "name")
    assert hasattr(Tool, "description")

    # Check that they are abstract
    assert Tool.name.__isabstractmethod__
    assert Tool.description.__isabstractmethod__


def test_tool_abstract_methods():
    """Test that Tool has expected abstract methods."""
    assert hasattr(Tool, "execute")

    # Check that it is abstract
    assert Tool.execute.__isabstractmethod__


def test_tool_implementation(mock_tool):
    """Test that mock_tool fixture works correctly."""
    assert mock_tool.name == "mock_tool"
    assert mock_tool.description == "Mock tool for testing"

    result = mock_tool.execute(param1="test")
    assert result.success is True
    assert result.output == {"result": "mock result"}

