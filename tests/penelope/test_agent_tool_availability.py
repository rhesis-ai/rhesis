"""
Tests to ensure tools are properly communicated to the LLM.

These tests validate that the LLM receives information about available tools,
preventing issues where the LLM hallucinates non-existent tool names.
"""

import pytest
from unittest.mock import Mock, patch

from rhesis.penelope.agent import PenelopeAgent
from rhesis.penelope.targets.base import Target, TargetResponse
from rhesis.sdk.models.base import BaseLLM


class TestToolAvailability:
    """Test that tools are properly made available to the LLM."""

    @pytest.fixture
    def mock_target(self):
        """Create a mock target."""
        target = Mock(spec=Target)
        target.target_type = "mock"
        target.target_id = "test-123"
        target.description = "Test target"
        target.validate_configuration.return_value = (True, None)
        target.get_tool_documentation.return_value = "Mock target documentation"
        target.send_message.return_value = TargetResponse(
            success=True,
            content="Response",
            session_id="session-123",
        )
        return target

    @pytest.fixture
    def mock_model(self):
        """Create a mock model that captures the system prompt."""
        mock = Mock(spec=BaseLLM)
        mock.get_model_name.return_value = "mock-model"
        
        # Return a valid response that will complete the test quickly
        mock.generate.return_value = {
            "reasoning": "Test complete",
            "tool_calls": [
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {"message": "Test message"},
                }
            ],
        }
        return mock

    def test_system_prompt_includes_tool_names(self, mock_model, mock_target):
        """Test that system prompt includes all available tool names."""
        agent = PenelopeAgent(model=mock_model, max_iterations=2)  # Allow at least one turn

        # Execute a test
        agent.execute_test(
            target=mock_target,
            goal="Test goal",
            instructions="Test instructions",
        )

        # Verify model.generate was called
        assert mock_model.generate.called, "model.generate was not called"
        
        # Get the FIRST call (from executor, not from metric evaluation)
        # call_args_list[0] is the first call, call_args is the last call
        first_call = mock_model.generate.call_args_list[0]
        call_kwargs = first_call.kwargs
        
        assert "system_prompt" in call_kwargs, (
            f"system_prompt not in first call kwargs. Available keys: {list(call_kwargs.keys())}"
        )
        system_prompt = call_kwargs["system_prompt"]

        # Verify all default tool names are in the system prompt
        assert "send_message_to_target" in system_prompt, (
            "System prompt must include 'send_message_to_target' tool name"
        )
        assert "analyze_response" in system_prompt, (
            "System prompt must include 'analyze_response' tool name"
        )
        assert "extract_information" in system_prompt, (
            "System prompt must include 'extract_information' tool name"
        )

    def test_system_prompt_includes_tool_descriptions(self, mock_model, mock_target):
        """Test that system prompt includes tool descriptions."""
        agent = PenelopeAgent(model=mock_model, max_iterations=2)

        agent.execute_test(
            target=mock_target,
            goal="Test goal",
            instructions="Test instructions",
        )

        # Get the FIRST call (from executor)
        first_call = mock_model.generate.call_args_list[0]
        system_prompt = first_call.kwargs["system_prompt"]

        # Verify tool descriptions are included (check for key phrases from tool descriptions)
        assert "Send a message to the test target" in system_prompt, (
            "System prompt must include send_message_to_target description"
        )
        assert "Available Tools:" in system_prompt, (
            "System prompt must have 'Available Tools:' section"
        )

    def test_system_prompt_not_empty_for_tools(self, mock_model, mock_target):
        """Test that available_tools parameter is not empty."""
        agent = PenelopeAgent(model=mock_model, max_iterations=2)

        with patch("rhesis.penelope.agent.get_system_prompt") as mock_get_prompt:
            mock_get_prompt.return_value = "Test prompt"
            
            agent.execute_test(
                target=mock_target,
                goal="Test goal",
                instructions="Test instructions",
            )

            # Verify get_system_prompt was called with non-empty available_tools
            assert mock_get_prompt.called
            call_kwargs = mock_get_prompt.call_args[1]
            
            assert "available_tools" in call_kwargs, (
                "get_system_prompt must be called with available_tools parameter"
            )
            assert call_kwargs["available_tools"] != "", (
                "available_tools parameter must not be empty - "
                "LLM needs to know what tools are available!"
            )
            assert "send_message_to_target" in call_kwargs["available_tools"], (
                "available_tools must include actual tool names"
            )

    def test_tool_documentation_format(self, mock_model, mock_target):
        """Test that tool documentation is properly formatted."""
        agent = PenelopeAgent(model=mock_model, max_iterations=2)

        agent.execute_test(
            target=mock_target,
            goal="Test goal",
            instructions="Test instructions",
        )

        # Get the FIRST call (from executor)
        first_call = mock_model.generate.call_args_list[0]
        system_prompt = first_call.kwargs["system_prompt"]

        # Verify markdown formatting for tools
        assert "### send_message_to_target" in system_prompt, (
            "Tool names should be formatted as markdown headers (### tool_name)"
        )

    def test_custom_tools_included_in_prompt(self, mock_model, mock_target):
        """Test that custom tools are also included in the system prompt."""
        from rhesis.penelope.tools.base import Tool, ToolResult

        class CustomTool(Tool):
            @property
            def name(self) -> str:
                return "custom_test_tool"

            @property
            def description(self) -> str:
                return "A custom tool for testing"

            def execute(self, **kwargs) -> ToolResult:
                return ToolResult(success=True, output={}, error=None)

        custom_tool = CustomTool()
        agent = PenelopeAgent(model=mock_model, tools=[custom_tool], max_iterations=2)

        agent.execute_test(
            target=mock_target,
            goal="Test goal",
            instructions="Test instructions",
        )

        # Get the FIRST call (from executor)
        first_call = mock_model.generate.call_args_list[0]
        system_prompt = first_call.kwargs["system_prompt"]

        # Verify custom tool is included
        assert "custom_test_tool" in system_prompt, (
            "Custom tools must be included in the system prompt"
        )
        assert "A custom tool for testing" in system_prompt, (
            "Custom tool descriptions must be included"
        )


class TestToolNameValidation:
    """Test that tool names in LLM responses are validated."""

    @pytest.fixture
    def mock_target(self):
        """Create a mock target."""
        target = Mock(spec=Target)
        target.target_type = "mock"
        target.target_id = "test-123"
        target.description = "Test target"
        target.validate_configuration.return_value = (True, None)
        target.get_tool_documentation.return_value = "Mock target documentation"
        target.send_message.return_value = TargetResponse(
            success=True,
            content="Response",
            session_id="session-123",
        )
        return target

    def test_invalid_tool_name_results_in_error(self, mock_target):
        """Test that using an invalid tool name results in a clear error."""
        mock_model = Mock(spec=BaseLLM)
        mock_model.get_model_name.return_value = "mock-model"
        
        # Simulate LLM generating an invalid tool name
        mock_model.generate.return_value = {
            "reasoning": "Using wrong tool name",
            "tool_calls": [
                {
                    "tool_name": "send_message",  # WRONG - should be send_message_to_target
                    "parameters": {"message": "Test"},
                }
            ],
        }

        agent = PenelopeAgent(model=mock_model, max_iterations=1)
        result = agent.execute_test(
            target=mock_target,
            goal="Test goal",
            instructions="Test instructions",
        )

        # Test should complete but with findings about unknown tool
        assert len(result.findings) > 0, "Should have findings about unknown tool"
        
        # Check that the error mentions the unknown tool
        findings_text = " ".join(result.findings)
        assert "send_message" in findings_text or "Unknown tool" in findings_text, (
            "Findings should mention the invalid tool name"
        )

    def test_hallucinated_tool_names_documented(self, mock_target):
        """Test that common hallucinated tool names are documented in findings."""
        mock_model = Mock(spec=BaseLLM)
        mock_model.get_model_name.return_value = "mock-model"
        
        # Test one specific hallucinated name that should be corrected
            mock_model.generate.return_value = {
                "reasoning": "Test",
                "tool_calls": [
                    {
                    "tool_name": "send_message",  # This should be corrected to send_message_to_target
                        "parameters": {"message": "Test"},
                    }
                ],
            }

            agent = PenelopeAgent(model=mock_model, max_iterations=1)
            result = agent.execute_test(
                target=mock_target,
                goal="Test goal",
                instructions="Test instructions",
            )

        # Should have findings about the invalid tool name correction
        assert len(result.findings) > 0, "Should have findings about invalid tool name: send_message"
        
        # Check that the finding mentions the tool name correction
        findings_text = " ".join(result.findings)
        assert "send_message" in findings_text or "invalid tool" in findings_text.lower(), (
            "Findings should mention the invalid tool name or correction"
            )

