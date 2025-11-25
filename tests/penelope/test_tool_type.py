"""Tests for ToolType enum and tool classification system."""

from rhesis.penelope.context import ToolType


class TestToolType:
    """Tests for ToolType enum and classification methods."""

    def test_tool_type_enum_values(self):
        """Test that all expected tool types are defined."""
        # Target interaction tools
        assert ToolType.SEND_MESSAGE_TO_TARGET == "send_message_to_target"
        assert ToolType.INVOKE_API_ENDPOINT == "invoke_api_endpoint"
        assert ToolType.SEND_WEBHOOK == "send_webhook"

        # Internal tools
        assert ToolType.ANALYZE_RESPONSE == "analyze_response"
        assert ToolType.EXTRACT_INFORMATION == "extract_information"
        assert ToolType.EVALUATE_OUTPUT == "evaluate_output"
        assert ToolType.CHECK_API_RESULT == "check_api_result"
        assert ToolType.VALIDATE_RESPONSE == "validate_response"

    def test_get_target_interaction_tools(self):
        """Test getting all target interaction tools."""
        target_tools = ToolType.get_target_interaction_tools()

        expected_tools = {
            "send_message_to_target",
            "invoke_api_endpoint",
            "send_webhook",
        }

        assert target_tools == expected_tools
        assert len(target_tools) == 3

    def test_get_internal_tools(self):
        """Test getting all internal tools."""
        internal_tools = ToolType.get_internal_tools()

        expected_tools = {
            "analyze_response",
            "extract_information",
            "evaluate_output",
            "check_api_result",
            "validate_response",
        }

        assert internal_tools == expected_tools
        assert len(internal_tools) == 5

    def test_is_target_interaction_true(self):
        """Test is_target_interaction for target interaction tools."""
        assert ToolType.is_target_interaction("send_message_to_target") is True
        assert ToolType.is_target_interaction("invoke_api_endpoint") is True
        assert ToolType.is_target_interaction("send_webhook") is True

    def test_is_target_interaction_false(self):
        """Test is_target_interaction for internal tools."""
        assert ToolType.is_target_interaction("analyze_response") is False
        assert ToolType.is_target_interaction("extract_information") is False
        assert ToolType.is_target_interaction("evaluate_output") is False
        assert ToolType.is_target_interaction("check_api_result") is False
        assert ToolType.is_target_interaction("validate_response") is False

    def test_is_target_interaction_unknown_tool(self):
        """Test is_target_interaction for unknown tools."""
        assert ToolType.is_target_interaction("unknown_tool") is False
        assert ToolType.is_target_interaction("") is False
        assert ToolType.is_target_interaction("random_string") is False

    def test_is_internal_tool_true(self):
        """Test is_internal_tool for internal tools."""
        assert ToolType.is_internal_tool("analyze_response") is True
        assert ToolType.is_internal_tool("extract_information") is True
        assert ToolType.is_internal_tool("evaluate_output") is True
        assert ToolType.is_internal_tool("check_api_result") is True
        assert ToolType.is_internal_tool("validate_response") is True

    def test_is_internal_tool_false(self):
        """Test is_internal_tool for target interaction tools."""
        assert ToolType.is_internal_tool("send_message_to_target") is False
        assert ToolType.is_internal_tool("invoke_api_endpoint") is False
        assert ToolType.is_internal_tool("send_webhook") is False

    def test_is_internal_tool_unknown_tool(self):
        """Test is_internal_tool for unknown tools."""
        assert ToolType.is_internal_tool("unknown_tool") is False
        assert ToolType.is_internal_tool("") is False
        assert ToolType.is_internal_tool("random_string") is False

    def test_tool_classification_mutual_exclusivity(self):
        """Test that tools are either target interaction or internal, never both."""
        all_target_tools = ToolType.get_target_interaction_tools()
        all_internal_tools = ToolType.get_internal_tools()

        # No overlap between the two sets
        overlap = all_target_tools.intersection(all_internal_tools)
        assert len(overlap) == 0, f"Tools should not be both target and internal: {overlap}"

    def test_tool_classification_completeness(self):
        """Test that every enum value is classified as either target or internal."""
        all_enum_values = {tool.value for tool in ToolType}
        all_classified_tools = ToolType.get_target_interaction_tools().union(
            ToolType.get_internal_tools()
        )

        assert all_enum_values == all_classified_tools, (
            f"All enum values should be classified. Missing: {all_enum_values - all_classified_tools}"
        )

    def test_generate_tool_description(self):
        """Test dynamic tool description generation."""
        description = ToolType.generate_tool_description()

        # Should contain section headers
        assert "TARGET INTERACTION TOOLS" in description
        assert "INTERNAL TOOLS" in description

        # Should contain all target interaction tools
        for tool in ToolType.get_target_interaction_tools():
            assert tool in description

        # Should contain all internal tools
        for tool in ToolType.get_internal_tools():
            assert tool in description

        # Should contain descriptions for each tool
        assert "Send a message to the target system" in description
        assert "Analyze a response from the target" in description
        assert "Extract specific information" in description

    def test_get_tool_description_individual_tools(self):
        """Test individual tool descriptions."""
        # Test a few specific tool descriptions
        assert "Send a message to the target system" in ToolType._get_tool_description(
            "send_message_to_target"
        )
        assert "Call an API endpoint directly" in ToolType._get_tool_description(
            "invoke_api_endpoint"
        )
        assert "Analyze a response from the target" in ToolType._get_tool_description(
            "analyze_response"
        )
        assert "Extract specific information" in ToolType._get_tool_description(
            "extract_information"
        )

        # Test unknown tool
        assert "Unknown tool" in ToolType._get_tool_description("unknown_tool")

    def test_tool_type_string_behavior(self):
        """Test that ToolType behaves as expected string enum."""
        # Can be used as strings (ToolType inherits from str, Enum)
        assert ToolType.SEND_MESSAGE_TO_TARGET.value == "send_message_to_target"
        assert ToolType.SEND_MESSAGE_TO_TARGET == "send_message_to_target"

        # Can be compared with strings
        tool_name = "analyze_response"
        assert tool_name == ToolType.ANALYZE_RESPONSE

        # Can be used in sets and dicts
        tool_set = {ToolType.SEND_MESSAGE_TO_TARGET, ToolType.ANALYZE_RESPONSE}
        assert "send_message_to_target" in tool_set
        assert "analyze_response" in tool_set

    def test_realistic_tool_classification_workflow(self):
        """Test realistic workflow of tool classification."""
        # Simulate processing a sequence of tools in a turn
        tool_sequence = [
            "analyze_response",  # Internal - should not complete turn
            "extract_information",  # Internal - should not complete turn
            "send_message_to_target",  # Target interaction - should complete turn
        ]

        turn_completed = False
        for tool_name in tool_sequence:
            if ToolType.is_target_interaction(tool_name):
                turn_completed = True
                break

        assert turn_completed is True

        # Test sequence with only internal tools
        internal_sequence = ["analyze_response", "extract_information", "evaluate_output"]

        turn_completed = False
        for tool_name in internal_sequence:
            if ToolType.is_target_interaction(tool_name):
                turn_completed = True
                break

        assert turn_completed is False

    def test_tool_type_case_sensitivity(self):
        """Test that tool type classification is case sensitive."""
        # Correct case should work
        assert ToolType.is_target_interaction("send_message_to_target") is True

        # Incorrect case should not work
        assert ToolType.is_target_interaction("Send_Message_To_Target") is False
        assert ToolType.is_target_interaction("SEND_MESSAGE_TO_TARGET") is False
        assert ToolType.is_target_interaction("sendMessageToTarget") is False
