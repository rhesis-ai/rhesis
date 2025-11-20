"""Tests for ResponseParser and validation components."""

from unittest.mock import Mock

import pytest
from rhesis.penelope.executor import ContextManager, ResponseParser, ToolCallIdGenerator


class TestResponseParser:
    """Tests for ResponseParser validation functionality."""

    def test_parse_tool_calls_valid_single_tool(self):
        """Test parsing valid response with single tool call."""
        response = {
            "reasoning": "Need to send a message",
            "tool_calls": [
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {"message": "Hello", "session_id": "test-123"},
                }
            ],
        }

        tool_calls = ResponseParser.parse_tool_calls(response)

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "send_message_to_target"
        assert tool_calls[0]["parameters"]["message"] == "Hello"
        assert tool_calls[0]["parameters"]["session_id"] == "test-123"

    def test_parse_tool_calls_valid_multiple_tools(self):
        """Test parsing valid response with multiple tool calls."""
        response = {
            "reasoning": "Need to analyze then respond",
            "tool_calls": [
                {
                    "tool_name": "analyze_response",
                    "parameters": {"response_text": "Hello", "analysis_focus": "tone"},
                },
                {"tool_name": "send_message_to_target", "parameters": {"message": "Hi there!"}},
            ],
        }

        tool_calls = ResponseParser.parse_tool_calls(response)

        assert len(tool_calls) == 2
        assert tool_calls[0]["tool_name"] == "analyze_response"
        assert tool_calls[1]["tool_name"] == "send_message_to_target"

    def test_parse_tool_calls_invalid_response_type(self):
        """Test parsing with invalid response type."""
        with pytest.raises(ValueError, match="Expected dict response"):
            ResponseParser.parse_tool_calls("invalid string response")

        with pytest.raises(ValueError, match="Expected dict response"):
            ResponseParser.parse_tool_calls(None)

        with pytest.raises(ValueError, match="Expected dict response"):
            ResponseParser.parse_tool_calls(123)

    def test_parse_tool_calls_missing_tool_calls(self):
        """Test parsing response missing tool_calls field."""
        response = {"reasoning": "Some reasoning"}

        with pytest.raises(ValueError, match="No tool calls found in response"):
            ResponseParser.parse_tool_calls(response)

    def test_parse_tool_calls_empty_tool_calls(self):
        """Test parsing response with empty tool_calls list."""
        response = {"reasoning": "Some reasoning", "tool_calls": []}

        with pytest.raises(ValueError, match="No tool calls found in response"):
            ResponseParser.parse_tool_calls(response)

    def test_parse_tool_calls_invalid_tool_calls_type(self):
        """Test parsing response with invalid tool_calls type."""
        response = {"reasoning": "Some reasoning", "tool_calls": "not a list"}

        with pytest.raises(ValueError, match="Expected tool_calls to be list"):
            ResponseParser.parse_tool_calls(response)

    def test_validate_tool_call_valid(self):
        """Test validating a valid tool call."""
        tool_call = {"tool_name": "send_message_to_target", "parameters": {"message": "Hello"}}

        validated = ResponseParser._validate_tool_call(tool_call, 0)

        assert validated["tool_name"] == "send_message_to_target"
        assert validated["parameters"]["message"] == "Hello"

    def test_validate_tool_call_invalid_type(self):
        """Test validating tool call with invalid type."""
        with pytest.raises(ValueError, match="Tool call 0 must be dict"):
            ResponseParser._validate_tool_call("not a dict", 0)

    def test_validate_tool_call_missing_tool_name(self):
        """Test validating tool call missing tool_name."""
        tool_call = {"parameters": {"message": "Hello"}}

        with pytest.raises(ValueError, match="Tool call 0 missing or invalid tool_name"):
            ResponseParser._validate_tool_call(tool_call, 0)

    def test_validate_tool_call_empty_tool_name(self):
        """Test validating tool call with empty tool_name."""
        tool_call = {"tool_name": "", "parameters": {}}

        with pytest.raises(ValueError, match="Tool call 0 missing or invalid tool_name"):
            ResponseParser._validate_tool_call(tool_call, 0)

    def test_validate_tool_call_invalid_tool_name_type(self):
        """Test validating tool call with non-string tool_name."""
        tool_call = {"tool_name": 123, "parameters": {}}

        with pytest.raises(ValueError, match="Tool call 0 missing or invalid tool_name"):
            ResponseParser._validate_tool_call(tool_call, 0)

    def test_validate_tool_call_missing_parameters(self):
        """Test validating tool call missing parameters (should default to empty dict)."""
        tool_call = {"tool_name": "test_tool"}

        validated = ResponseParser._validate_tool_call(tool_call, 0)

        assert validated["tool_name"] == "test_tool"
        assert validated["parameters"] == {}

    def test_validate_tool_call_invalid_parameters_type(self):
        """Test validating tool call with invalid parameters type."""
        tool_call = {"tool_name": "test_tool", "parameters": "not a dict"}

        with pytest.raises(ValueError, match="Tool call 0 parameters must be dict"):
            ResponseParser._validate_tool_call(tool_call, 0)

    def test_parse_tool_calls_multiple_validation_errors(self):
        """Test parsing with multiple tool calls where some are invalid."""
        response = {
            "reasoning": "Multiple tools",
            "tool_calls": [
                {"tool_name": "valid_tool", "parameters": {"param": "value"}},
                {"tool_name": "", "parameters": {}},  # Invalid: empty tool_name
                {"parameters": {"param": "value"}},  # Invalid: missing tool_name
            ],
        }

        # Should fail on the first invalid tool call
        with pytest.raises(ValueError, match="Tool call 1 missing or invalid tool_name"):
            ResponseParser.parse_tool_calls(response)

    def test_parse_tool_calls_complex_parameters(self):
        """Test parsing tool calls with complex parameter structures."""
        response = {
            "reasoning": "Complex parameters",
            "tool_calls": [
                {
                    "tool_name": "complex_tool",
                    "parameters": {
                        "nested": {"key": "value", "number": 42},
                        "list": [1, 2, 3, "string"],
                        "boolean": True,
                        "null_value": None,
                    },
                }
            ],
        }

        tool_calls = ResponseParser.parse_tool_calls(response)

        assert len(tool_calls) == 1
        params = tool_calls[0]["parameters"]
        assert params["nested"]["key"] == "value"
        assert params["nested"]["number"] == 42
        assert params["list"] == [1, 2, 3, "string"]
        assert params["boolean"] is True
        assert params["null_value"] is None


class TestToolCallIdGenerator:
    """Tests for ToolCallIdGenerator functionality."""

    def test_generate_id_default_format(self):
        """Test generating ID with default format."""
        tool_id = ToolCallIdGenerator.generate_id(0, "test_tool")
        assert tool_id == "call_1_test_tool"

        tool_id = ToolCallIdGenerator.generate_id(4, "send_message_to_target")
        assert tool_id == "call_5_send_message_to_target"

    def test_generate_id_custom_format(self):
        """Test generating ID with custom format template."""
        tool_id = ToolCallIdGenerator.generate_id(2, "analyze_response", "exec_{count}_{tool}_id")
        assert tool_id == "exec_3_analyze_response_id"

        tool_id = ToolCallIdGenerator.generate_id(0, "test", "{tool}_{count}")
        assert tool_id == "test_1"

    def test_generate_uuid_id(self):
        """Test generating UUID-based ID."""
        tool_id = ToolCallIdGenerator.generate_uuid_id("test_tool")

        # Should start with tool name
        assert tool_id.startswith("test_tool_")

        # Should have UUID suffix (8 hex characters)
        suffix = tool_id.split("_", 2)[-1]
        assert len(suffix) == 8
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_generate_uuid_id_uniqueness(self):
        """Test that UUID-based IDs are unique."""
        ids = set()
        for _ in range(100):
            tool_id = ToolCallIdGenerator.generate_uuid_id("test_tool")
            ids.add(tool_id)

        # All IDs should be unique
        assert len(ids) == 100

    def test_generate_id_edge_cases(self):
        """Test ID generation with edge cases."""
        # Zero execution count
        tool_id = ToolCallIdGenerator.generate_id(0, "tool")
        assert tool_id == "call_1_tool"

        # Empty tool name
        tool_id = ToolCallIdGenerator.generate_id(0, "")
        assert tool_id == "call_1_"

        # Tool name with special characters
        tool_id = ToolCallIdGenerator.generate_id(0, "tool-with_special.chars")
        assert tool_id == "call_1_tool-with_special.chars"


class TestContextManager:
    """Tests for ContextManager functionality."""

    def create_mock_messages(self, count: int):
        """Helper to create mock messages."""
        messages = []
        for i in range(count):
            msg = Mock()
            msg.content = f"Message {i + 1}"
            messages.append(msg)
        return messages

    def test_select_context_messages_recent_strategy(self):
        """Test selecting context messages with recent strategy."""
        messages = self.create_mock_messages(10)

        # Select last 5 messages
        selected = ContextManager.select_context_messages(
            messages, max_messages=5, strategy="recent"
        )

        assert len(selected) == 5
        assert selected[0].content == "Message 6"
        assert selected[-1].content == "Message 10"

    def test_select_context_messages_no_limit(self):
        """Test selecting context messages without limit."""
        messages = self.create_mock_messages(3)

        selected = ContextManager.select_context_messages(messages)

        assert len(selected) == 3
        assert selected == messages

    def test_select_context_messages_limit_larger_than_available(self):
        """Test selecting context messages when limit is larger than available."""
        messages = self.create_mock_messages(3)

        selected = ContextManager.select_context_messages(
            messages, max_messages=10, strategy="recent"
        )

        assert len(selected) == 3
        assert selected == messages

    def test_select_context_messages_empty_list(self):
        """Test selecting context messages from empty list."""
        selected = ContextManager.select_context_messages([], max_messages=5)
        assert selected == []

    def test_select_context_messages_zero_limit(self):
        """Test selecting context messages with zero limit."""
        messages = self.create_mock_messages(5)

        selected = ContextManager.select_context_messages(
            messages, max_messages=0, strategy="recent"
        )

        assert selected == []

    def test_select_context_messages_fallback_strategies(self):
        """Test that unsupported strategies fall back to recent."""
        messages = self.create_mock_messages(10)

        # Test "relevant" strategy (should fallback to recent)
        selected = ContextManager.select_context_messages(
            messages, max_messages=3, strategy="relevant"
        )
        assert len(selected) == 3
        assert selected[-1].content == "Message 10"  # Most recent

        # Test "balanced" strategy (should fallback to recent)
        selected = ContextManager.select_context_messages(
            messages, max_messages=3, strategy="balanced"
        )
        assert len(selected) == 3
        assert selected[-1].content == "Message 10"  # Most recent

    def test_select_context_messages_invalid_strategy(self):
        """Test selecting context messages with invalid strategy."""
        messages = self.create_mock_messages(5)

        with pytest.raises(ValueError, match="Unknown context strategy"):
            ContextManager.select_context_messages(
                messages, max_messages=3, strategy="invalid_strategy"
            )

    def test_select_context_messages_default_config(self):
        """Test that default max_messages comes from config when not provided."""
        messages = self.create_mock_messages(20)

        # Should use DEFAULT_CONTEXT_WINDOW_MESSAGES from config
        selected = ContextManager.select_context_messages(messages)

        # Default should be 10 (from PenelopeConfig.DEFAULT_CONTEXT_WINDOW_MESSAGES)
        assert len(selected) == 10
        assert selected[-1].content == "Message 20"  # Most recent
