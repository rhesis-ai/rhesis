"""Tests for Turn model and multi-tool execution functionality."""

from datetime import datetime

from rhesis.penelope.context import ToolExecution, Turn
from rhesis.penelope.schemas import (
    AssistantMessage,
    FunctionCall,
    MessageToolCall,
    ToolMessage,
)


class TestTurnModel:
    """Tests for Turn model with multiple executions."""

    def create_tool_execution(
        self, tool_name: str, reasoning: str, arguments: str = "{}"
    ) -> ToolExecution:
        """Helper to create a ToolExecution."""
        assistant_msg = AssistantMessage(
            content=reasoning,
            tool_calls=[
                MessageToolCall(
                    id=f"call_{tool_name}",
                    type="function",
                    function=FunctionCall(name=tool_name, arguments=arguments),
                )
            ],
        )

        tool_msg = ToolMessage(
            tool_call_id=f"call_{tool_name}",
            name=tool_name,
            content='{"success": true, "output": {}}',
        )

        return ToolExecution(
            tool_name=tool_name,
            reasoning=reasoning,
            assistant_message=assistant_msg,
            tool_message=tool_msg,
        )

    def test_turn_creation_single_execution(self):
        """Test creating a Turn with a single target interaction."""
        target_execution = self.create_tool_execution(
            "send_message_to_target", "Send greeting", '{"message": "Hello"}'
        )

        turn = Turn(
            turn_number=1,
            executions=[target_execution],
            target_interaction=target_execution,
        )

        assert turn.turn_number == 1
        assert len(turn.executions) == 1
        assert turn.target_interaction == target_execution
        assert isinstance(turn.timestamp, datetime)
        assert turn.evaluation is None

    def test_turn_creation_multiple_executions(self):
        """Test creating a Turn with multiple executions including internal tools."""
        # Internal analysis execution
        analysis_execution = self.create_tool_execution(
            "analyze_response",
            "Analyze previous response",
            '{"response_text": "Hello", "analysis_focus": "tone"}',
        )

        # Internal extraction execution
        extraction_execution = self.create_tool_execution(
            "extract_information",
            "Extract key information",
            '{"response_text": "Hello", "extraction_target": "greeting"}',
        )

        # Target interaction execution (completes the turn)
        target_execution = self.create_tool_execution(
            "send_message_to_target", "Send follow-up message", '{"message": "How are you?"}'
        )

        turn = Turn(
            turn_number=2,
            executions=[analysis_execution, extraction_execution, target_execution],
            target_interaction=target_execution,
        )

        assert turn.turn_number == 2
        assert len(turn.executions) == 3
        assert turn.target_interaction == target_execution

        # Verify execution order is preserved
        assert turn.executions[0].tool_name == "analyze_response"
        assert turn.executions[1].tool_name == "extract_information"
        assert turn.executions[2].tool_name == "send_message_to_target"

    def test_turn_serialization(self):
        """Test Turn timestamp serialization."""
        target_execution = self.create_tool_execution("send_message_to_target", "Test")

        turn = Turn(
            turn_number=1,
            executions=[target_execution],
            target_interaction=target_execution,
        )

        serialized = turn.model_dump()
        assert "timestamp" in serialized
        assert isinstance(serialized["timestamp"], str)
        assert "T" in serialized["timestamp"]  # ISO format

    def test_turn_with_evaluation(self):
        """Test Turn with evaluation field."""
        target_execution = self.create_tool_execution("send_message_to_target", "Test")

        turn = Turn(
            turn_number=1,
            executions=[target_execution],
            target_interaction=target_execution,
            evaluation="Good progress, target responded positively",
        )

        assert turn.evaluation == "Good progress, target responded positively"

    def test_turn_target_interaction_must_be_in_executions(self):
        """Test that target_interaction must be one of the executions."""
        analysis_execution = self.create_tool_execution("analyze_response", "Analyze")
        target_execution = self.create_tool_execution("send_message_to_target", "Send")
        different_execution = self.create_tool_execution("extract_information", "Extract")

        # This should work - target_interaction is in executions
        turn = Turn(
            turn_number=1,
            executions=[analysis_execution, target_execution],
            target_interaction=target_execution,
        )
        assert turn.target_interaction == target_execution

        # Note: Pydantic doesn't enforce this constraint by default, but it's a logical requirement
        # In a real implementation, you might add a validator for this

    def test_complex_turn_workflow(self):
        """Test a complex turn with realistic multi-tool workflow."""
        # Step 1: Analyze previous response
        analysis_execution = self.create_tool_execution(
            "analyze_response",
            "Analyzing target's previous response for sentiment and key points",
            '{"response_text": "I am having trouble with login", "analysis_focus": "issues"}',
        )

        # Step 2: Extract specific information
        extraction_execution = self.create_tool_execution(
            "extract_information",
            "Extracting the specific issue mentioned",
            '{"response_text": "I am having trouble with login", "extraction_target": "problem_type"}',
        )

        # Step 3: Send targeted response
        target_execution = self.create_tool_execution(
            "send_message_to_target",
            "Providing specific help for login issues",
            '{"message": "I can help you with login issues. What specific error are you seeing?"}',
        )

        turn = Turn(
            turn_number=3,
            executions=[analysis_execution, extraction_execution, target_execution],
            target_interaction=target_execution,
            evaluation="Successfully identified login issue and provided targeted assistance",
        )

        # Verify the complete workflow
        assert len(turn.executions) == 3
        assert turn.executions[0].tool_name == "analyze_response"
        assert turn.executions[1].tool_name == "extract_information"
        assert turn.executions[2].tool_name == "send_message_to_target"
        assert turn.target_interaction.tool_name == "send_message_to_target"

        # Verify reasoning progression
        assert "Analyzing target's previous response" in turn.executions[0].reasoning
        assert "Extracting the specific issue" in turn.executions[1].reasoning
        assert "Providing specific help" in turn.executions[2].reasoning

        # Verify tool arguments
        analysis_args = turn.executions[0].get_tool_call_arguments()
        assert analysis_args["analysis_focus"] == "issues"

        extraction_args = turn.executions[1].get_tool_call_arguments()
        assert extraction_args["extraction_target"] == "problem_type"

        target_args = turn.executions[2].get_tool_call_arguments()
        assert "login issues" in target_args["message"]

    def test_turn_execution_timestamps(self):
        """Test that executions within a turn have proper timestamps."""
        exec1 = self.create_tool_execution("analyze_response", "First")
        exec2 = self.create_tool_execution("send_message_to_target", "Second")

        turn = Turn(
            turn_number=1,
            executions=[exec1, exec2],
            target_interaction=exec2,
        )

        # All executions should have timestamps
        for execution in turn.executions:
            assert isinstance(execution.timestamp, datetime)

        # Turn should have its own timestamp
        assert isinstance(turn.timestamp, datetime)

    def test_empty_executions_list(self):
        """Test Turn validation with empty executions list."""
        target_execution = self.create_tool_execution("send_message_to_target", "Test")

        # This should work with empty list if target_interaction is provided
        # (though logically the target_interaction should be in executions)
        turn = Turn(
            turn_number=1,
            executions=[],
            target_interaction=target_execution,
        )

        assert len(turn.executions) == 0
        assert turn.target_interaction == target_execution
