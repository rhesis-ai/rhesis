"""Integration tests for multi-tool execution within single turns."""

import json
from unittest.mock import Mock

import pytest
from rhesis.penelope.context import TestContext, TestState
from rhesis.penelope.executor import TurnExecutor
from rhesis.penelope.tools.base import Tool, ToolResult

from rhesis.sdk.models.base import BaseLLM


class TestMultiToolExecution:
    """Integration tests for multi-tool execution functionality."""

    @pytest.fixture
    def mock_model(self):
        """Mock LLM model that returns multi-tool responses."""
        mock = Mock(spec=BaseLLM)
        mock.get_model_name.return_value = "mock-model"
        return mock

    @pytest.fixture
    def test_state(self):
        """Create test state for multi-tool execution tests."""
        context = TestContext(
            target_id="test",
            target_type="test",
            instructions="Test multi-tool execution",
            goal="Test goal",
        )
        return TestState(context=context)

    @pytest.fixture
    def mock_tools(self):
        """Create mock tools for testing."""
        tools = {}

        # Analysis tool (internal)
        analysis_tool = Mock(spec=Tool)
        analysis_tool.name = "analyze_response"
        analysis_tool.execute.return_value = ToolResult(
            success=True, output={"sentiment": "positive", "confidence": 0.8}, error=None
        )
        tools["analyze_response"] = analysis_tool

        # Extraction tool (internal)
        extraction_tool = Mock(spec=Tool)
        extraction_tool.name = "extract_information"
        extraction_tool.execute.return_value = ToolResult(
            success=True, output={"extracted": "key information"}, error=None
        )
        tools["extract_information"] = extraction_tool

        # Target interaction tool
        target_tool = Mock(spec=Tool)
        target_tool.name = "send_message_to_target"
        target_tool.execute.return_value = ToolResult(
            success=True, output={"response": "Message sent successfully"}, error=None
        )
        tools["send_message_to_target"] = target_tool

        return list(tools.values())

    def test_single_tool_execution_completes_turn(self, mock_model, test_state, mock_tools):
        """Test that a single target interaction tool completes a turn."""
        # Model returns single target interaction tool
        mock_model.generate.return_value = {
            "reasoning": "Send greeting to target",
            "tool_calls": [
                {"tool_name": "send_message_to_target", "parameters": {"message": "Hello"}}
            ],
        }

        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(
            state=test_state, tools=mock_tools, system_prompt="Test prompt"
        )

        assert success is True
        assert test_state.current_turn == 1  # Turn completed
        assert len(test_state.turns) == 1
        assert len(test_state.current_turn_executions) == 0  # Cleared after turn completion

        # Verify turn structure
        turn = test_state.turns[0]
        assert len(turn.executions) == 1
        assert turn.target_interaction.tool_name == "send_message_to_target"

    def test_multiple_internal_tools_no_turn_completion(self, mock_model, test_state, mock_tools):
        """Test that multiple internal tools don't complete a turn."""
        # Model returns only internal tools
        mock_model.generate.return_value = {
            "reasoning": "Analyze and extract information",
            "tool_calls": [
                {
                    "tool_name": "analyze_response",
                    "parameters": {"response_text": "Hello", "analysis_focus": "tone"},
                },
                {
                    "tool_name": "extract_information",
                    "parameters": {"response_text": "Hello", "extraction_target": "greeting"},
                },
            ],
        }

        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(
            state=test_state, tools=mock_tools, system_prompt="Test prompt"
        )

        assert success is True
        assert test_state.current_turn == 0  # No turn completed
        assert len(test_state.turns) == 0
        assert len(test_state.current_turn_executions) == 2  # Both executions stored

        # Verify executions
        exec1 = test_state.current_turn_executions[0]
        exec2 = test_state.current_turn_executions[1]
        assert exec1.tool_name == "analyze_response"
        assert exec2.tool_name == "extract_information"

    def test_mixed_tools_completes_turn_on_target_interaction(
        self, mock_model, test_state, mock_tools
    ):
        """Test that mixed internal + target interaction tools complete turn properly."""
        # Model returns internal tools followed by target interaction
        mock_model.generate.return_value = {
            "reasoning": "Analyze, extract, then respond to target",
            "tool_calls": [
                {
                    "tool_name": "analyze_response",
                    "parameters": {"response_text": "Hello", "analysis_focus": "sentiment"},
                },
                {
                    "tool_name": "extract_information",
                    "parameters": {"response_text": "Hello", "extraction_target": "key_points"},
                },
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {"message": "Based on analysis, here's my response"},
                },
            ],
        }

        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(
            state=test_state, tools=mock_tools, system_prompt="Test prompt"
        )

        assert success is True
        assert test_state.current_turn == 1  # Turn completed
        assert len(test_state.turns) == 1
        assert len(test_state.current_turn_executions) == 0  # Cleared after completion

        # Verify turn contains all executions
        turn = test_state.turns[0]
        assert len(turn.executions) == 3
        assert turn.executions[0].tool_name == "analyze_response"
        assert turn.executions[1].tool_name == "extract_information"
        assert turn.executions[2].tool_name == "send_message_to_target"
        assert turn.target_interaction.tool_name == "send_message_to_target"

        # Verify all tools were called
        for tool in mock_tools:
            if tool.name in ["analyze_response", "extract_information", "send_message_to_target"]:
                tool.execute.assert_called_once()

    def test_target_interaction_early_completes_turn_immediately(
        self, mock_model, test_state, mock_tools
    ):
        """Test that target interaction tool completes turn even if it's not last."""
        # Model returns target interaction first, then internal tools
        mock_model.generate.return_value = {
            "reasoning": "Send message first, then analyze",
            "tool_calls": [
                {"tool_name": "send_message_to_target", "parameters": {"message": "Hello"}},
                {
                    "tool_name": "analyze_response",
                    "parameters": {"response_text": "Hello", "analysis_focus": "tone"},
                },
            ],
        }

        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(
            state=test_state, tools=mock_tools, system_prompt="Test prompt"
        )

        assert success is True
        assert test_state.current_turn == 1  # Turn completed after first tool
        assert len(test_state.turns) == 1

        # Turn should contain only the first execution (target interaction)
        turn = test_state.turns[0]
        assert len(turn.executions) == 1
        assert turn.executions[0].tool_name == "send_message_to_target"
        assert turn.target_interaction.tool_name == "send_message_to_target"

        # Only the target interaction tool should have been called
        target_tool = next(t for t in mock_tools if t.name == "send_message_to_target")
        analysis_tool = next(t for t in mock_tools if t.name == "analyze_response")

        target_tool.execute.assert_called_once()
        analysis_tool.execute.assert_not_called()  # Should not be called

    def test_multiple_turns_with_mixed_executions(self, mock_model, test_state, mock_tools):
        """Test multiple turns each with different execution patterns."""
        executor = TurnExecutor(model=mock_model)

        # Turn 1: Single target interaction
        mock_model.generate.return_value = {
            "reasoning": "Simple greeting",
            "tool_calls": [
                {"tool_name": "send_message_to_target", "parameters": {"message": "Hello"}}
            ],
        }

        success = executor.execute_turn(state=test_state, tools=mock_tools, system_prompt="Test")
        assert success is True
        assert test_state.current_turn == 1

        # Turn 2: Internal analysis then target interaction
        mock_model.generate.return_value = {
            "reasoning": "Analyze then respond",
            "tool_calls": [
                {
                    "tool_name": "analyze_response",
                    "parameters": {"response_text": "Response", "analysis_focus": "sentiment"},
                },
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {"message": "Follow-up message"},
                },
            ],
        }

        success = executor.execute_turn(state=test_state, tools=mock_tools, system_prompt="Test")
        assert success is True
        assert test_state.current_turn == 2

        # Verify both turns
        assert len(test_state.turns) == 2

        turn1 = test_state.turns[0]
        assert len(turn1.executions) == 1
        assert turn1.target_interaction.tool_name == "send_message_to_target"

        turn2 = test_state.turns[1]
        assert len(turn2.executions) == 2
        assert turn2.executions[0].tool_name == "analyze_response"
        assert turn2.executions[1].tool_name == "send_message_to_target"
        assert turn2.target_interaction.tool_name == "send_message_to_target"

    def test_tool_execution_order_preserved(self, mock_model, test_state, mock_tools):
        """Test that tool execution order is preserved in turn."""
        # Model returns tools in specific order
        mock_model.generate.return_value = {
            "reasoning": "Execute tools in specific order",
            "tool_calls": [
                {
                    "tool_name": "extract_information",
                    "parameters": {"response_text": "Text", "extraction_target": "info"},
                },
                {
                    "tool_name": "analyze_response",
                    "parameters": {"response_text": "Text", "analysis_focus": "tone"},
                },
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {"message": "Response based on analysis"},
                },
            ],
        }

        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(state=test_state, tools=mock_tools, system_prompt="Test")

        assert success is True
        turn = test_state.turns[0]

        # Verify execution order is preserved
        assert turn.executions[0].tool_name == "extract_information"
        assert turn.executions[1].tool_name == "analyze_response"
        assert turn.executions[2].tool_name == "send_message_to_target"

    def test_tool_execution_with_failures(self, mock_model, test_state, mock_tools):
        """Test multi-tool execution when some tools fail."""
        # Make analysis tool fail
        analysis_tool = next(t for t in mock_tools if t.name == "analyze_response")
        analysis_tool.execute.return_value = ToolResult(
            success=False, output={}, error="Analysis failed"
        )

        mock_model.generate.return_value = {
            "reasoning": "Try analysis then send message",
            "tool_calls": [
                {
                    "tool_name": "analyze_response",
                    "parameters": {"response_text": "Text", "analysis_focus": "tone"},
                },
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {"message": "Sending despite analysis failure"},
                },
            ],
        }

        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(state=test_state, tools=mock_tools, system_prompt="Test")

        assert success is True  # Turn should still succeed
        turn = test_state.turns[0]

        # Both executions should be recorded
        assert len(turn.executions) == 2

        # Verify failure is recorded in tool message
        analysis_result = json.loads(turn.executions[0].tool_message.content)
        assert analysis_result["success"] is False
        assert "Analysis failed" in analysis_result["error"]

        # Target interaction should still succeed
        target_result = json.loads(turn.executions[1].tool_message.content)
        assert target_result["success"] is True

    def test_conversation_history_updated_correctly(self, mock_model, test_state, mock_tools):
        """Test that conversation history is updated correctly with multi-tool turns."""
        mock_model.generate.return_value = {
            "reasoning": "Multi-tool conversation",
            "tool_calls": [
                {
                    "tool_name": "analyze_response",
                    "parameters": {"response_text": "Hello", "analysis_focus": "tone"},
                },
                {"tool_name": "send_message_to_target", "parameters": {"message": "Hi there!"}},
            ],
        }

        # Mock target tool to return a response
        target_tool = next(t for t in mock_tools if t.name == "send_message_to_target")
        target_tool.execute.return_value = ToolResult(
            success=True, output={"response": "Hello back!"}, error=None
        )

        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(state=test_state, tools=mock_tools, system_prompt="Test")

        assert success is True

        # Conversation should have one entry (combined user + assistant message)
        assert len(test_state.conversation.messages) == 1
        
        # Should contain the combined conversation entry
        conversation_msg = test_state.conversation.messages[0]
        
        # The conversation contains both the user message and assistant response
        assert "Hi there!" in conversation_msg.content
        assert "Hello back!" in conversation_msg.content
