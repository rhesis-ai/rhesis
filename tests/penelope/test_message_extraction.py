"""Tests for message extraction from target interactions."""

import pytest
from rhesis.penelope.context import TestContext, TestState, ToolExecution, ToolType
from rhesis.penelope.schemas import (
    AssistantMessage,
    FunctionCall,
    MessageToolCall,
    ToolMessage,
)


class TestMessageExtraction:
    """Tests for _extract_penelope_message_from_interaction method."""

    @pytest.fixture
    def test_state(self):
        """Create test state for message extraction tests."""
        context = TestContext(
            target_id="test",
            target_type="test",
            instructions="Test message extraction",
            goal="Test goal",
        )
        return TestState(context=context)

    def create_tool_execution(self, tool_name: str, arguments: str) -> ToolExecution:
        """Helper to create a ToolExecution with specific arguments."""
        assistant_msg = AssistantMessage(
            content="Test reasoning",
            tool_calls=[
                MessageToolCall(
                    id="call_1",
                    type="function",
                    function=FunctionCall(name=tool_name, arguments=arguments),
                )
            ],
        )

        tool_msg = ToolMessage(
            tool_call_id="call_1",
            name=tool_name,
            content='{"success": true, "output": {}}',
        )

        return ToolExecution(
            tool_name=tool_name,
            reasoning="Test reasoning",
            assistant_message=assistant_msg,
            tool_message=tool_msg,
        )

    def test_extract_send_message_to_target(self, test_state):
        """Test extracting message from send_message_to_target tool."""
        execution = self.create_tool_execution(
            ToolType.SEND_MESSAGE_TO_TARGET,
            '{"message": "Hello world", "session_id": "test-123"}'
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        assert message == "Hello world"
        assert session_id == "test-123"

    def test_extract_send_message_to_target_no_session(self, test_state):
        """Test extracting message from send_message_to_target without session_id."""
        execution = self.create_tool_execution(
            ToolType.SEND_MESSAGE_TO_TARGET,
            '{"message": "Hello without session"}'
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        assert message == "Hello without session"
        assert session_id is None

    def test_extract_invoke_api_endpoint(self, test_state):
        """Test extracting message from invoke_api_endpoint tool."""
        execution = self.create_tool_execution(
            ToolType.INVOKE_API_ENDPOINT,
            '{"endpoint": "/api/test", "data": {"key": "value"}}'
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        assert message == {"key": "value"}
        assert session_id is None

    def test_extract_invoke_api_endpoint_no_data(self, test_state):
        """Test extracting message from invoke_api_endpoint without data field."""
        execution = self.create_tool_execution(
            ToolType.INVOKE_API_ENDPOINT,
            '{"endpoint": "/api/test", "method": "POST"}'
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        # Should fall back to string representation of all args
        assert "endpoint" in message
        assert "method" in message
        assert session_id is None

    def test_extract_send_webhook(self, test_state):
        """Test extracting message from send_webhook tool."""
        execution = self.create_tool_execution(
            ToolType.SEND_WEBHOOK,
            '{"url": "https://example.com/webhook", "payload": {"event": "test"}}'
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        assert message == {"event": "test"}
        assert session_id is None

    def test_extract_send_webhook_no_payload(self, test_state):
        """Test extracting message from send_webhook without payload field."""
        execution = self.create_tool_execution(
            ToolType.SEND_WEBHOOK,
            '{"url": "https://example.com/webhook", "method": "POST"}'
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        # Should fall back to string representation of all args
        assert "url" in message
        assert "method" in message
        assert session_id is None

    def test_extract_unknown_tool_type(self, test_state):
        """Test extracting message from unknown tool type."""
        execution = self.create_tool_execution(
            "unknown_tool",
            '{"param1": "value1", "param2": "value2"}'
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        assert message.startswith("unknown_tool:")
        assert "param1" in message
        assert "param2" in message
        assert session_id is None

    def test_extract_empty_arguments(self, test_state):
        """Test extracting message with empty arguments."""
        execution = self.create_tool_execution(
            ToolType.SEND_MESSAGE_TO_TARGET,
            '{}'
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        assert message == ""  # Empty message field
        assert session_id is None

    def test_extract_invalid_json_arguments(self, test_state):
        """Test extracting message with invalid JSON arguments."""
        # Create execution with invalid JSON
        assistant_msg = AssistantMessage(
            content="Test reasoning",
            tool_calls=[
                MessageToolCall(
                    id="call_1",
                    type="function",
                    function=FunctionCall(
                        name=ToolType.SEND_MESSAGE_TO_TARGET,
                        arguments="invalid json"
                    ),
                )
            ],
        )

        tool_msg = ToolMessage(
            tool_call_id="call_1",
            name=ToolType.SEND_MESSAGE_TO_TARGET,
            content='{"success": true}',
        )

        execution = ToolExecution(
            tool_name=ToolType.SEND_MESSAGE_TO_TARGET,
            reasoning="Test reasoning",
            assistant_message=assistant_msg,
            tool_message=tool_msg,
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        # Should handle gracefully and return empty message
        assert message == ""
        assert session_id is None

    def test_extract_no_tool_calls(self, test_state):
        """Test extracting message when no tool calls exist."""
        assistant_msg = AssistantMessage(content="Test reasoning", tool_calls=None)

        tool_msg = ToolMessage(
            tool_call_id="call_1",
            name=ToolType.SEND_MESSAGE_TO_TARGET,
            content='{"success": true}',
        )

        execution = ToolExecution(
            tool_name=ToolType.SEND_MESSAGE_TO_TARGET,
            reasoning="Test reasoning",
            assistant_message=assistant_msg,
            tool_message=tool_msg,
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        # Should handle gracefully and return empty message
        assert message == ""
        assert session_id is None

    def test_extract_api_endpoint_fallback_to_empty(self, test_state):
        """Test API endpoint extraction when no arguments at all."""
        # Create execution with no arguments
        assistant_msg = AssistantMessage(content="Test reasoning", tool_calls=None)

        tool_msg = ToolMessage(
            tool_call_id="call_1",
            name=ToolType.INVOKE_API_ENDPOINT,
            content='{"success": true}',
        )

        execution = ToolExecution(
            tool_name=ToolType.INVOKE_API_ENDPOINT,
            reasoning="Test reasoning",
            assistant_message=assistant_msg,
            tool_message=tool_msg,
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        assert message == "API call"  # Fallback message
        assert session_id is None

    def test_extract_webhook_fallback_to_empty(self, test_state):
        """Test webhook extraction when no arguments at all."""
        # Create execution with no arguments
        assistant_msg = AssistantMessage(content="Test reasoning", tool_calls=None)

        tool_msg = ToolMessage(
            tool_call_id="call_1",
            name=ToolType.SEND_WEBHOOK,
            content='{"success": true}',
        )

        execution = ToolExecution(
            tool_name=ToolType.SEND_WEBHOOK,
            reasoning="Test reasoning",
            assistant_message=assistant_msg,
            tool_message=tool_msg,
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        assert message == "Webhook call"  # Fallback message
        assert session_id is None

    def test_extract_unknown_tool_fallback_to_empty(self, test_state):
        """Test unknown tool extraction when no arguments at all."""
        # Create execution with no arguments
        assistant_msg = AssistantMessage(content="Test reasoning", tool_calls=None)

        tool_msg = ToolMessage(
            tool_call_id="call_1",
            name="mystery_tool",
            content='{"success": true}',
        )

        execution = ToolExecution(
            tool_name="mystery_tool",
            reasoning="Test reasoning",
            assistant_message=assistant_msg,
            tool_message=tool_msg,
        )

        message, session_id = test_state._extract_penelope_message_from_interaction(execution)

        assert message == "Unknown interaction"  # Fallback message
        assert session_id is None
