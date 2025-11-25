"""Tests for ToolExecution model and functionality."""

import json
from datetime import datetime

from rhesis.penelope.context import ToolExecution
from rhesis.penelope.schemas import (
    AssistantMessage,
    FunctionCall,
    MessageToolCall,
    ToolMessage,
)


class TestToolExecution:
    """Tests for ToolExecution model."""

    def test_tool_execution_creation(self):
        """Test creating a ToolExecution instance."""
        assistant_msg = AssistantMessage(
            content="Testing tool execution",
            tool_calls=[
                MessageToolCall(
                    id="call_1",
                    type="function",
                    function=FunctionCall(
                        name="send_message_to_target",
                        arguments='{"message": "Hello", "session_id": "test-123"}',
                    ),
                )
            ],
        )

        tool_msg = ToolMessage(
            tool_call_id="call_1",
            name="send_message_to_target",
            content='{"success": true, "output": {"response": "Hello back"}}',
        )

        execution = ToolExecution(
            tool_name="send_message_to_target",
            reasoning="Send greeting to target",
            assistant_message=assistant_msg,
            tool_message=tool_msg,
        )

        assert execution.tool_name == "send_message_to_target"
        assert execution.reasoning == "Send greeting to target"
        assert execution.assistant_message == assistant_msg
        assert execution.tool_message == tool_msg
        assert isinstance(execution.timestamp, datetime)

    def test_tool_execution_serialization(self):
        """Test ToolExecution timestamp serialization."""
        execution = ToolExecution(
            tool_name="test_tool",
            reasoning="Test reasoning",
            assistant_message=AssistantMessage(content="Test"),
            tool_message=ToolMessage(tool_call_id="call_1", name="test_tool", content="{}"),
        )

        # Test that timestamp can be serialized
        serialized = execution.model_dump()
        assert "timestamp" in serialized
        assert isinstance(serialized["timestamp"], str)
        # Should be ISO format
        assert "T" in serialized["timestamp"]

    def test_get_tool_call_arguments_success(self):
        """Test extracting tool call arguments successfully."""
        assistant_msg = AssistantMessage(
            content="Test",
            tool_calls=[
                MessageToolCall(
                    id="call_1",
                    type="function",
                    function=FunctionCall(
                        name="send_message_to_target",
                        arguments='{"message": "Hello", "session_id": "test-123"}',
                    ),
                )
            ],
        )

        execution = ToolExecution(
            tool_name="send_message_to_target",
            reasoning="Test",
            assistant_message=assistant_msg,
            tool_message=ToolMessage(
                tool_call_id="call_1", name="send_message_to_target", content="{}"
            ),
        )

        args = execution.get_tool_call_arguments()
        assert args == {"message": "Hello", "session_id": "test-123"}

    def test_get_tool_call_arguments_specific_tool(self):
        """Test extracting arguments for a specific tool name."""
        assistant_msg = AssistantMessage(
            content="Test",
            tool_calls=[
                MessageToolCall(
                    id="call_1",
                    type="function",
                    function=FunctionCall(
                        name="analyze_response",
                        arguments='{"response_text": "Hello", "analysis_focus": "tone"}',
                    ),
                ),
                MessageToolCall(
                    id="call_2",
                    type="function",
                    function=FunctionCall(
                        name="send_message_to_target", arguments='{"message": "Hi there"}'
                    ),
                ),
            ],
        )

        execution = ToolExecution(
            tool_name="send_message_to_target",
            reasoning="Test",
            assistant_message=assistant_msg,
            tool_message=ToolMessage(
                tool_call_id="call_2", name="send_message_to_target", content="{}"
            ),
        )

        # Get arguments for analyze_response tool
        args = execution.get_tool_call_arguments("analyze_response")
        assert args == {"response_text": "Hello", "analysis_focus": "tone"}

        # Get arguments for send_message_to_target tool (default)
        args = execution.get_tool_call_arguments()
        assert args == {"message": "Hi there"}

    def test_get_tool_call_arguments_no_tool_calls(self):
        """Test extracting arguments when no tool calls exist."""
        assistant_msg = AssistantMessage(content="Test", tool_calls=None)

        execution = ToolExecution(
            tool_name="test_tool",
            reasoning="Test",
            assistant_message=assistant_msg,
            tool_message=ToolMessage(tool_call_id="call_1", name="test_tool", content="{}"),
        )

        args = execution.get_tool_call_arguments()
        assert args == {}

    def test_get_tool_call_arguments_tool_not_found(self):
        """Test extracting arguments for a tool that doesn't exist."""
        assistant_msg = AssistantMessage(
            content="Test",
            tool_calls=[
                MessageToolCall(
                    id="call_1",
                    type="function",
                    function=FunctionCall(name="different_tool", arguments='{"param": "value"}'),
                )
            ],
        )

        execution = ToolExecution(
            tool_name="send_message_to_target",
            reasoning="Test",
            assistant_message=assistant_msg,
            tool_message=ToolMessage(
                tool_call_id="call_1", name="send_message_to_target", content="{}"
            ),
        )

        args = execution.get_tool_call_arguments("nonexistent_tool")
        assert args == {}

    def test_get_tool_call_arguments_invalid_json(self):
        """Test extracting arguments with invalid JSON."""
        assistant_msg = AssistantMessage(
            content="Test",
            tool_calls=[
                MessageToolCall(
                    id="call_1",
                    type="function",
                    function=FunctionCall(name="test_tool", arguments="invalid json"),
                )
            ],
        )

        execution = ToolExecution(
            tool_name="test_tool",
            reasoning="Test",
            assistant_message=assistant_msg,
            tool_message=ToolMessage(tool_call_id="call_1", name="test_tool", content="{}"),
        )

        args = execution.get_tool_call_arguments()
        assert args == {}

    def test_tool_execution_with_internal_tool(self):
        """Test ToolExecution with an internal analysis tool."""
        assistant_msg = AssistantMessage(
            content="Analyzing the response for sentiment",
            tool_calls=[
                MessageToolCall(
                    id="call_1",
                    type="function",
                    function=FunctionCall(
                        name="analyze_response",
                        arguments='{"response_text": "Great job!", "analysis_focus": "sentiment"}',
                    ),
                )
            ],
        )

        tool_msg = ToolMessage(
            tool_call_id="call_1",
            name="analyze_response",
            content='{"success": true, "output": {"sentiment": "positive", "confidence": 0.95}}',
        )

        execution = ToolExecution(
            tool_name="analyze_response",
            reasoning="Analyzing the response for sentiment",
            assistant_message=assistant_msg,
            tool_message=tool_msg,
        )

        assert execution.tool_name == "analyze_response"
        args = execution.get_tool_call_arguments()
        assert args["response_text"] == "Great job!"
        assert args["analysis_focus"] == "sentiment"

        # Verify tool result
        result = json.loads(execution.tool_message.content)
        assert result["success"] is True
        assert result["output"]["sentiment"] == "positive"
