"""Tests for Penelope executor module."""

import json
from unittest.mock import Mock, patch

import pytest
from rhesis.penelope.context import TestContext, TestState
from rhesis.penelope.executor import TurnExecutor
from rhesis.penelope.schemas import AssistantMessage, ToolMessage
from rhesis.penelope.tools.base import Tool, ToolResult

from rhesis.sdk.models.base import BaseLLM


@pytest.fixture
def mock_model():
    """Mock LLM model for testing."""
    mock = Mock(spec=BaseLLM)
    mock.get_model_name.return_value = "mock-model"
    mock.generate.return_value = {
        "reasoning": "Test reasoning",
        "tool_calls": [
            {
                "tool_name": "send_message_to_target",  # Use target interaction tool
                "parameters": {"param1": "value1"},
            }
        ],
    }
    return mock


@pytest.fixture
def test_state():
    """Create test state."""
    context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test instructions",
        goal="Test goal",
    )
    return TestState(context=context)


@pytest.fixture
def mock_tool():
    """Mock tool for testing."""
    tool = Mock(spec=Tool)
    tool.name = "send_message_to_target"  # Match the tool name in responses
    tool.execute.return_value = ToolResult(success=True, output={"result": "success"}, error=None)
    return tool


class TestTurnExecutorInitialization:
    """Tests for TurnExecutor initialization."""

    def test_init_with_defaults(self, mock_model):
        """Test TurnExecutor initialization with default values."""
        executor = TurnExecutor(model=mock_model)

        assert executor.model == mock_model
        assert executor.verbose is False
        assert executor.enable_transparency is True

    def test_init_with_custom_values(self, mock_model):
        """Test TurnExecutor initialization with custom values."""
        executor = TurnExecutor(model=mock_model, verbose=True, enable_transparency=False)

        assert executor.model == mock_model
        assert executor.verbose is True
        assert executor.enable_transparency is False


class TestTurnExecutorExecuteTurn:
    """Tests for TurnExecutor.execute_turn method."""

    def test_execute_turn_first_turn(self, mock_model, test_state, mock_tool):
        """Test execute_turn on first turn."""
        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[mock_tool], system_prompt="System prompt"
        )

        # Verify success
        assert success is True

        # Verify model.generate was called
        mock_model.generate.assert_called_once()
        call_args = mock_model.generate.call_args

        # Check system prompt
        assert call_args[1]["system_prompt"] == "System prompt"

        # Verify tool was executed
        mock_tool.execute.assert_called_once_with(param1="value1")

        # Verify turn was added to state
        assert test_state.current_turn == 1
        assert len(test_state.turns) == 1

    def test_execute_turn_subsequent_turn(self, mock_model, test_state, mock_tool):
        """Test execute_turn on subsequent turn."""
        # Add first turn
        test_state.current_turn = 1

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[mock_tool], system_prompt="System prompt"
        )

        # Verify success
        assert success is True

        # Verify turn counter incremented
        assert test_state.current_turn == 2

    def test_execute_turn_calls_correct_tool(self, mock_model, test_state):
        """Test execute_turn calls the correct tool based on LLM response."""
        # Create multiple tools
        tool1 = Mock(spec=Tool)
        tool1.name = "tool1"
        tool1.execute.return_value = ToolResult(success=True, output={}, error=None)

        tool2 = Mock(spec=Tool)
        tool2.name = "tool2"
        tool2.execute.return_value = ToolResult(success=True, output={}, error=None)

        # Model selects tool2
        mock_model.generate.return_value = {
            "reasoning": "Use tool2",
            "tool_calls": [
                {
                    "tool_name": "tool2",
                    "parameters": {"arg": "value"},
                }
            ],
        }

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[tool1, tool2], system_prompt="System prompt"
        )

        # Verify tool2 was called, not tool1
        tool1.execute.assert_not_called()
        tool2.execute.assert_called_once_with(arg="value")
        assert success is True

    def test_execute_turn_handles_model_error(self, mock_model, test_state, mock_tool):
        """Test execute_turn handles model generation errors."""
        # Make model raise exception
        mock_model.generate.side_effect = RuntimeError("Model error")

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[mock_tool], system_prompt="System prompt"
        )

        # Verify failure
        assert success is False

        # Verify error was recorded
        assert len(test_state.findings) > 0
        assert "Model generation failed" in test_state.findings[0]

        # Verify tool was not executed
        mock_tool.execute.assert_not_called()

    def test_execute_turn_handles_unknown_tool(self, mock_model, test_state, mock_tool):
        """Test execute_turn handles unknown tool gracefully."""
        # Model requests unknown tool
        mock_model.generate.return_value = {
            "reasoning": "Use unknown tool",
            "tool_calls": [
                {
                    "tool_name": "unknown_tool",
                    "parameters": {},
                }
            ],
        }

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[mock_tool], system_prompt="System prompt"
        )

        # Should still succeed but tool result indicates error
        assert success is True

        # Verify execution was added (but no turn completed since unknown_tool is not a target interaction)
        assert len(test_state.current_turn_executions) == 1
        assert len(test_state.turns) == 0  # No turn completed

        # Check the execution that was added
        execution = test_state.current_turn_executions[0]
        tool_result = json.loads(execution.tool_message.content)
        assert tool_result["success"] is False
        assert "Unknown tool" in tool_result["error"]

    def test_execute_turn_handles_invalid_response_type(self, mock_model, test_state, mock_tool):
        """Test execute_turn handles invalid response type from model."""
        # Model returns invalid type
        mock_model.generate.return_value = "invalid string response"

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[mock_tool], system_prompt="System prompt"
        )

        # Verify failure
        assert success is False

        # Verify error was recorded
        assert len(test_state.findings) > 0
        assert "Invalid model response type" in test_state.findings[0]

    def test_execute_turn_handles_tool_failure(self, mock_model, test_state, mock_tool):
        """Test execute_turn handles tool execution failure."""
        # Tool fails
        mock_tool.execute.return_value = ToolResult(
            success=False, output={}, error="Tool execution failed"
        )

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[mock_tool], system_prompt="System prompt"
        )

        # Turn should still execute successfully
        assert success is True

        # Verify tool result contains error
        turn = test_state.turns[0]
        tool_result = json.loads(turn.target_interaction.tool_message.content)
        assert tool_result["success"] is False
        assert tool_result["error"] == "Tool execution failed"

    def test_execute_turn_updates_conversation(self, mock_model, test_state, mock_tool):
        """Test execute_turn updates conversation history."""
        # Setup mock tool with send_message_to_target
        interaction_tool = Mock(spec=Tool)
        interaction_tool.name = "send_message_to_target"
        interaction_tool.execute.return_value = ToolResult(
            success=True, output={"response": "Hello back"}, error=None
        )

        mock_model.generate.return_value = {
            "reasoning": "Send greeting",
            "tool_calls": [
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {"message": "Hello"},
                }
            ],
        }

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[interaction_tool], system_prompt="System prompt"
        )

        # Verify conversation was updated
        assert success is True
        # The conversation should be updated via state.add_turn -> _update_conversation_from_turn

    def test_execute_turn_with_verbose_mode(self, mock_model, test_state, mock_tool):
        """Test execute_turn in verbose mode displays information."""
        executor = TurnExecutor(model=mock_model, verbose=True, enable_transparency=True)

        with patch("rhesis.penelope.executor.display_turn") as mock_display:
            success = executor.execute_turn(
                state=test_state, tools=[mock_tool], system_prompt="System prompt"
            )

            # Verify display_turn was called
            assert success is True
            mock_display.assert_called_once()

    def test_execute_turn_without_transparency(self, mock_model, test_state, mock_tool):
        """Test execute_turn without transparency doesn't display turn."""
        executor = TurnExecutor(model=mock_model, verbose=True, enable_transparency=False)

        with patch("rhesis.penelope.executor.display_turn") as mock_display:
            success = executor.execute_turn(
                state=test_state, tools=[mock_tool], system_prompt="System prompt"
            )

            # Verify display_turn was not called
            assert success is True
            mock_display.assert_not_called()

    def test_execute_turn_with_pydantic_parameters(self, mock_model, test_state, mock_tool):
        """Test execute_turn handles Pydantic model parameters."""
        # Create mock Pydantic parameters
        mock_params = Mock()
        mock_params.model_dump.return_value = {"param1": "value1"}

        mock_model.generate.return_value = {
            "reasoning": "Test with Pydantic",
            "tool_calls": [
                {
                    "tool_name": "send_message_to_target",  # Use target interaction tool
                    "parameters": {"param1": "value1"},  # Use dict directly
                }
            ],
        }

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[mock_tool], system_prompt="System prompt"
        )

        # Verify success
        assert success is True

        # Verify tool was called with the parameters
        mock_tool.execute.assert_called_once_with(param1="value1")

    def test_execute_turn_creates_proper_message_structure(self, mock_model, test_state, mock_tool):
        """Test execute_turn creates proper AssistantMessage and ToolMessage."""
        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[mock_tool], system_prompt="System prompt"
        )

        # Verify turn structure
        assert success is True
        assert len(test_state.turns) == 1

        turn = test_state.turns[0]

        # Verify AssistantMessage
        assert isinstance(turn.target_interaction.assistant_message, AssistantMessage)
        assert turn.target_interaction.assistant_message.content == "Test reasoning"
        assert len(turn.target_interaction.assistant_message.tool_calls) == 1
        assert (
            turn.target_interaction.assistant_message.tool_calls[0].function.name
            == "send_message_to_target"
        )

        # Verify ToolMessage
        assert isinstance(turn.target_interaction.tool_message, ToolMessage)
        assert (
            turn.target_interaction.tool_message.name == "send_message_to_target"
        )  # Updated to match fixture
        tool_result = json.loads(turn.target_interaction.tool_message.content)
        assert tool_result["success"] is True

    def test_execute_turn_with_empty_tool_name(self, mock_model, test_state, mock_tool):
        """Test execute_turn handles empty tool_name."""
        mock_model.generate.return_value = {
            "reasoning": "No tool",
            "tool_calls": [
                {
                    "tool_name": "",
                    "parameters": {},
                }
            ],
        }

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[mock_tool], system_prompt="System prompt"
        )

        # Should fail due to validation (empty tool name is invalid)
        assert success is False

        # Should have added a finding about the invalid response
        assert len(test_state.findings) > 0
        assert "Invalid response format" in test_state.findings[0]


class TestTurnExecutorEdgeCases:
    """Tests for edge cases in TurnExecutor."""

    def test_execute_turn_with_complex_parameters(self, mock_model, test_state):
        """Test execute_turn with complex nested parameters."""
        complex_tool = Mock(spec=Tool)
        complex_tool.name = "complex_tool"
        complex_tool.execute.return_value = ToolResult(success=True, output={}, error=None)

        mock_model.generate.return_value = {
            "reasoning": "Complex params",
            "tool_calls": [
                {
                    "tool_name": "complex_tool",
                    "parameters": {
                        "nested": {"key": "value"},
                        "list": [1, 2, 3],
                        "bool": True,
                    },
                }
            ],
        }

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[complex_tool], system_prompt="System prompt"
        )

        # Verify complex params were passed
        assert success is True
        complex_tool.execute.assert_called_once()
        call_kwargs = complex_tool.execute.call_args[1]
        assert call_kwargs["nested"]["key"] == "value"
        assert call_kwargs["list"] == [1, 2, 3]
        assert call_kwargs["bool"] is True

    def test_execute_turn_preserves_reasoning(self, mock_model, test_state, mock_tool):
        """Test execute_turn preserves reasoning in turn."""
        detailed_reasoning = "This is a detailed explanation of why we chose this action."

        mock_model.generate.return_value = {
            "reasoning": detailed_reasoning,
            "tool_calls": [
                {
                    "tool_name": "send_message_to_target",  # Use target interaction tool
                    "parameters": {},
                }
            ],
        }

        executor = TurnExecutor(model=mock_model)

        success = executor.execute_turn(
            state=test_state, tools=[mock_tool], system_prompt="System prompt"
        )

        # Verify reasoning is preserved
        assert success is True
        assert test_state.turns[0].target_interaction.reasoning == detailed_reasoning
        assert (
            test_state.turns[0].target_interaction.assistant_message.content == detailed_reasoning
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
