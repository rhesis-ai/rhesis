"""Tests for base Tool class."""

import pytest
from rhesis.penelope.tools.base import Tool, ToolParameter, ToolResult


def test_tool_parameter_creation():
    """Test ToolParameter initialization."""
    param = ToolParameter(
        name="test_param",
        type="string",
        description="Test parameter description",
        required=True,
        examples=["example1", "example2"],
    )

    assert param.name == "test_param"
    assert param.type == "string"
    assert param.description == "Test parameter description"
    assert param.required is True
    assert param.examples == ["example1", "example2"]


def test_tool_parameter_defaults():
    """Test ToolParameter default values."""
    param = ToolParameter(
        name="test_param",
        type="string",
        description="Test description",
    )

    assert param.required is False
    assert param.examples is None


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
    assert hasattr(Tool, "parameters")

    # Check that they are abstract
    assert Tool.name.__isabstractmethod__
    assert Tool.description.__isabstractmethod__
    assert Tool.parameters.__isabstractmethod__


def test_tool_abstract_methods():
    """Test that Tool has expected abstract methods."""
    assert hasattr(Tool, "execute")

    # Check that it is abstract
    assert Tool.execute.__isabstractmethod__


def test_tool_concrete_methods(mock_tool):
    """Test Tool concrete methods (get_schema, validate_input)."""
    # Test get_schema
    schema = mock_tool.get_schema()

    assert "name" in schema
    assert schema["name"] == "mock_tool"
    assert "description" in schema
    assert "parameters" in schema
    assert "type" in schema["parameters"]
    assert "properties" in schema["parameters"]
    assert "required" in schema["parameters"]

    # Check that param1 is in properties and required
    assert "param1" in schema["parameters"]["properties"]
    assert "param1" in schema["parameters"]["required"]


def test_tool_validate_input_missing_required(mock_tool):
    """Test validate_input with missing required parameter."""
    is_valid, error = mock_tool.validate_input()

    assert is_valid is False
    assert "Missing required parameter" in error
    assert "param1" in error


def test_tool_validate_input_unknown_parameter(mock_tool):
    """Test validate_input with unknown parameter."""
    is_valid, error = mock_tool.validate_input(
        param1="value", unknown_param="value"
    )

    assert is_valid is False
    assert "Unknown parameter" in error
    assert "unknown_param" in error


def test_tool_validate_input_success(mock_tool):
    """Test validate_input with valid parameters."""
    is_valid, error = mock_tool.validate_input(param1="value")

    assert is_valid is True
    assert error is None


def test_tool_implementation(mock_tool):
    """Test that mock_tool fixture works correctly."""
    assert mock_tool.name == "mock_tool"
    assert mock_tool.description == "Mock tool for testing"
    assert len(mock_tool.parameters) == 1
    assert mock_tool.parameters[0].name == "param1"

    result = mock_tool.execute(param1="test")
    assert result.success is True
    assert result.output == {"result": "mock result"}


def test_tool_get_schema_optional_parameters():
    """Test get_schema with optional parameters."""

    class TestTool(Tool):
        @property
        def name(self) -> str:
            return "test_tool"

        @property
        def description(self) -> str:
            return "Test tool"

        @property
        def parameters(self):
            return [
                ToolParameter(
                    name="required_param",
                    type="string",
                    description="Required",
                    required=True,
                ),
                ToolParameter(
                    name="optional_param",
                    type="string",
                    description="Optional",
                    required=False,
                ),
            ]

        def execute(self, **kwargs):
            return ToolResult(success=True, output={})

    tool = TestTool()
    schema = tool.get_schema()

    # Only required_param should be in required list
    assert len(schema["parameters"]["required"]) == 1
    assert "required_param" in schema["parameters"]["required"]
    assert "optional_param" not in schema["parameters"]["required"]

    # Both should be in properties
    assert "required_param" in schema["parameters"]["properties"]
    assert "optional_param" in schema["parameters"]["properties"]

