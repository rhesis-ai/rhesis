"""Tests for MCP schema validation."""

import pytest
from pydantic import ValidationError

from rhesis.sdk.services.mcp.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolCall,
    ToolResult,
)


@pytest.mark.unit
class TestToolCall:
    """Test ToolCall schema"""

    def test_tool_call_valid(self):
        """Test valid ToolCall creation"""
        tool_call = ToolCall(tool_name="search_pages", arguments='{"query": "test"}')

        assert tool_call.tool_name == "search_pages"
        assert tool_call.arguments == {"query": "test"}

    def test_tool_call_with_empty_arguments(self):
        """Test ToolCall with empty arguments"""
        tool_call = ToolCall(tool_name="list_tools", arguments="{}")

        assert tool_call.tool_name == "list_tools"
        assert tool_call.arguments == {}

    def test_tool_call_parse_invalid_json(self):
        """Test ToolCall with invalid JSON defaults to empty dict"""
        tool_call = ToolCall(tool_name="test_tool", arguments="invalid json{")

        assert tool_call.tool_name == "test_tool"
        assert tool_call.arguments == {}

    def test_tool_call_with_dict_arguments(self):
        """Test ToolCall with dict arguments (already parsed)"""
        tool_call = ToolCall(tool_name="test", arguments={"key": "value"})

        assert tool_call.arguments == {"key": "value"}

    def test_tool_call_extra_fields_forbidden(self):
        """Test ToolCall rejects extra fields"""
        with pytest.raises(ValidationError):
            ToolCall(tool_name="test", arguments="{}", extra_field="not allowed")


@pytest.mark.unit
class TestToolResult:
    """Test ToolResult schema"""

    def test_tool_result_success(self):
        """Test successful ToolResult"""
        result = ToolResult(tool_name="search_pages", success=True, content="Found 5 pages")

        assert result.tool_name == "search_pages"
        assert result.success is True
        assert result.content == "Found 5 pages"
        assert result.error is None

    def test_tool_result_failure(self):
        """Test failed ToolResult"""
        result = ToolResult(tool_name="search_pages", success=False, error="Resource not found")

        assert result.tool_name == "search_pages"
        assert result.success is False
        assert result.error == "Resource not found"
        assert result.content == ""

    def test_tool_result_minimal(self):
        """Test ToolResult with minimal fields"""
        result = ToolResult(tool_name="test", success=True)

        assert result.tool_name == "test"
        assert result.success is True
        assert result.content == ""
        assert result.error is None


@pytest.mark.unit
class TestAgentAction:
    """Test AgentAction schema"""

    def test_agent_action_call_tool(self):
        """Test AgentAction with call_tool action"""
        tool_call = ToolCall(tool_name="search", arguments="{}")
        action = AgentAction(
            reasoning="I need to search for pages",
            action="call_tool",
            tool_calls=[tool_call],
        )

        assert action.action == "call_tool"
        assert len(action.tool_calls) == 1
        assert action.tool_calls[0].tool_name == "search"
        assert action.final_answer is None

    def test_agent_action_finish(self):
        """Test AgentAction with finish action"""
        action = AgentAction(
            reasoning="I have the answer",
            action="finish",
            final_answer="The answer is 42",
        )

        assert action.action == "finish"
        assert action.final_answer == "The answer is 42"
        assert action.tool_calls == []

    def test_agent_action_invalid_action(self):
        """Test AgentAction rejects invalid action"""
        with pytest.raises(ValidationError):
            AgentAction(reasoning="Test", action="invalid_action")


@pytest.mark.unit
class TestExecutionStep:
    """Test ExecutionStep schema"""

    def test_execution_step_valid(self):
        """Test valid ExecutionStep creation"""
        tool_call = ToolCall(tool_name="test", arguments="{}")
        tool_result = ToolResult(tool_name="test", success=True, content="Result")

        step = ExecutionStep(
            iteration=1,
            reasoning="First step",
            action="call_tool",
            tool_calls=[tool_call],
            tool_results=[tool_result],
        )

        assert step.iteration == 1
        assert step.reasoning == "First step"
        assert step.action == "call_tool"
        assert len(step.tool_calls) == 1
        assert len(step.tool_results) == 1

    def test_execution_step_minimal(self):
        """Test ExecutionStep with minimal fields"""
        step = ExecutionStep(iteration=1, reasoning="Test", action="finish")

        assert step.iteration == 1
        assert step.tool_calls == []
        assert step.tool_results == []


@pytest.mark.unit
class TestAgentResult:
    """Test AgentResult schema"""

    def test_agent_result_success(self):
        """Test successful AgentResult"""
        step = ExecutionStep(iteration=1, reasoning="Done", action="finish")
        result = AgentResult(
            final_answer="Success",
            execution_history=[step],
            iterations_used=1,
            max_iterations_reached=False,
            success=True,
        )

        assert result.final_answer == "Success"
        assert len(result.execution_history) == 1
        assert result.iterations_used == 1
        assert result.max_iterations_reached is False
        assert result.success is True
        assert result.error is None

    def test_agent_result_failure(self):
        """Test failed AgentResult"""
        result = AgentResult(
            final_answer="",
            execution_history=[],
            iterations_used=0,
            max_iterations_reached=False,
            success=False,
            error="Agent failed",
        )

        assert result.success is False
        assert result.error == "Agent failed"

    def test_agent_result_max_iterations(self):
        """Test AgentResult with max iterations reached"""
        result = AgentResult(
            final_answer="",
            execution_history=[],
            iterations_used=10,
            max_iterations_reached=True,
            success=False,
        )

        assert result.max_iterations_reached is True
        assert result.iterations_used == 10
