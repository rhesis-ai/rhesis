"""Tests for MCPAgent class."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.mcp.agent import MCPAgent
from rhesis.sdk.services.mcp.exceptions import (
    MCPApplicationError,
    MCPConnectionError,
    MCPValidationError,
)
from rhesis.sdk.services.mcp.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolCall,
    ToolResult,
)


@pytest.mark.unit
class TestMCPAgent:
    """Test MCPAgent class"""

    @pytest.fixture
    def mock_mcp_client(self):
        """Create a mock MCP client"""
        client = Mock()
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        return client

    @pytest.fixture
    def mock_model(self):
        """Create a mock LLM model"""
        model = Mock(spec=BaseLLM)
        model.generate = Mock(return_value={})
        return model

    @pytest.fixture
    def agent(self, mock_mcp_client, mock_model):
        """Create MCPAgent instance"""
        return MCPAgent(model=mock_model, mcp_client=mock_mcp_client, verbose=False)

    def test_agent_initialization(self, mock_mcp_client, mock_model):
        """Test agent initialization"""
        agent = MCPAgent(
            model=mock_model, mcp_client=mock_mcp_client, max_iterations=15, verbose=True
        )

        assert agent.model == mock_model
        assert agent.mcp_client == mock_mcp_client
        assert agent.max_iterations == 15
        assert agent.verbose is True
        assert agent.executor is not None

    def test_agent_initialization_without_client_raises(self, mock_model):
        """Test agent initialization without client raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            MCPAgent(model=mock_model, mcp_client=None)

        assert "mcp_client is required" in str(exc_info.value)

    def test_agent_initialization_with_string_model(self, mock_mcp_client):
        """Test agent initialization with string model name"""
        with patch("rhesis.sdk.services.mcp.agent.get_model") as mock_get_model:
            mock_model = Mock()
            mock_get_model.return_value = mock_model

            agent = MCPAgent(model="gpt-4", mcp_client=mock_mcp_client)

            assert agent.model == mock_model
            mock_get_model.assert_called_once_with("gpt-4")

    def test_agent_loads_default_system_prompt(self, mock_mcp_client, mock_model):
        """Test agent loads default system prompt"""
        with patch("rhesis.sdk.services.mcp.agent.jinja2.Environment") as mock_jinja:
            mock_template = Mock()
            mock_template.render.return_value = "Default prompt"
            mock_env = Mock()
            mock_env.get_template.return_value = mock_template
            mock_jinja.return_value = mock_env

            agent = MCPAgent(model=mock_model, mcp_client=mock_mcp_client)

            assert agent.system_prompt == "Default prompt"

    def test_agent_uses_custom_system_prompt(self, mock_mcp_client, mock_model):
        """Test agent uses custom system prompt"""
        custom_prompt = "Custom system prompt"
        agent = MCPAgent(model=mock_model, mcp_client=mock_mcp_client, system_prompt=custom_prompt)

        assert agent.system_prompt == custom_prompt

    @pytest.mark.asyncio
    async def test_run_async_success_finish_action(self, agent, mock_mcp_client, mock_model):
        """Test successful agent run with finish action"""
        # Mock available tools
        mock_executor = Mock()
        mock_executor.get_available_tools = AsyncMock(return_value=[])
        agent.executor = mock_executor

        # Mock LLM response - finish action
        action = AgentAction(
            reasoning="I have the answer",
            action="finish",
            final_answer="The answer is 42",
        )
        mock_model.generate.return_value = action.model_dump()

        result = await agent.run_async("What is the answer?")

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.final_answer == "The answer is 42"
        assert result.iterations_used == 1
        assert result.max_iterations_reached is False
        mock_mcp_client.connect.assert_called_once()
        mock_mcp_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_async_success_with_tool_call(self, agent, mock_mcp_client, mock_model):
        """Test successful agent run with tool call"""
        # Mock available tools
        mock_executor = Mock()
        mock_executor.get_available_tools = AsyncMock(
            return_value=[{"name": "search", "description": "Search tool"}]
        )
        mock_executor.execute_tool = AsyncMock(
            return_value=ToolResult(tool_name="search", success=True, content="Found results")
        )
        agent.executor = mock_executor

        # Mock LLM responses as dicts (simulating what LLM would return)
        # First iteration: call tool
        action1_dict = {
            "reasoning": "I need to search",
            "action": "call_tool",
            "tool_calls": [{"tool_name": "search", "arguments": '{"query": "test"}'}],
            "final_answer": None,
        }
        # Second iteration: finish
        action2_dict = {
            "reasoning": "I have the answer",
            "action": "finish",
            "tool_calls": [],
            "final_answer": "Results found",
        }

        mock_model.generate.side_effect = [action1_dict, action2_dict]

        result = await agent.run_async("Search for test")

        assert result.success is True
        assert result.iterations_used == 2
        mock_executor.execute_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_async_max_iterations_reached(self, agent, mock_mcp_client, mock_model):
        """Test agent stops at max iterations"""
        agent.max_iterations = 2

        # Mock available tools
        mock_executor = Mock()
        mock_executor.get_available_tools = AsyncMock(return_value=[])
        mock_executor.execute_tool = AsyncMock(
            return_value=ToolResult(tool_name="test", success=True, content="Result")
        )
        agent.executor = mock_executor

        # Always return call_tool action (never finishes)
        action_dict = {
            "reasoning": "Keep going",
            "action": "call_tool",
            "tool_calls": [{"tool_name": "test", "arguments": "{}"}],
            "final_answer": None,
        }
        mock_model.generate.return_value = action_dict

        with pytest.raises(MCPValidationError) as exc_info:
            await agent.run_async("Test query")

        assert "iterations" in str(exc_info.value).lower()
        assert mock_model.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_run_async_connection_error(self, agent, mock_mcp_client, mock_model):
        """Test agent handles connection errors"""
        mock_mcp_client.connect.side_effect = ConnectionError("Connection failed")

        with pytest.raises(MCPConnectionError):
            await agent.run_async("Test query")

    @pytest.mark.asyncio
    async def test_run_async_application_error(self, agent, mock_mcp_client, mock_model):
        """Test agent handles application errors"""
        # Mock available tools
        mock_executor = Mock()
        mock_executor.get_available_tools = AsyncMock(return_value=[])
        agent.executor = mock_executor

        action_dict = {
            "reasoning": "Call tool",
            "action": "call_tool",
            "tool_calls": [{"tool_name": "test", "arguments": "{}"}],
            "final_answer": None,
        }
        mock_model.generate.return_value = action_dict

        mock_executor.execute_tool.side_effect = MCPApplicationError(
            status_code=500, detail="Server error"
        )

        with pytest.raises(MCPApplicationError):
            await agent.run_async("Test query")

    @pytest.mark.asyncio
    async def test_run_async_llm_parsing_error(self, agent, mock_mcp_client, mock_model):
        """Test agent handles LLM parsing errors"""
        # Mock available tools
        mock_executor = Mock()
        mock_executor.get_available_tools = AsyncMock(return_value=[])
        agent.executor = mock_executor

        # LLM returns invalid response
        mock_model.generate.side_effect = ValueError("Parse error")

        result = await agent.run_async("Test query")

        assert result.success is False
        assert "Failed to parse LLM response" in result.error or "execution failed" in result.error

    @pytest.mark.asyncio
    async def test_run_async_tool_failure_recoverable(self, agent, mock_mcp_client, mock_model):
        """Test agent handles recoverable tool failures"""
        # Mock available tools
        mock_executor = Mock()
        mock_executor.get_available_tools = AsyncMock(return_value=[])
        agent.executor = mock_executor

        # First iteration: call tool (fails)
        action1_dict = {
            "reasoning": "Try tool",
            "action": "call_tool",
            "tool_calls": [{"tool_name": "test", "arguments": "{}"}],
            "final_answer": None,
        }
        # Second iteration: finish (after failure)
        action2_dict = {
            "reasoning": "Tool failed, but I can answer",
            "action": "finish",
            "tool_calls": [],
            "final_answer": "Answer without tool",
        }

        mock_model.generate.side_effect = [action1_dict, action2_dict]

        # Tool returns failure (not exception)
        mock_executor.execute_tool = AsyncMock(
            return_value=ToolResult(tool_name="test", success=False, error="Tool failed")
        )

        result = await agent.run_async("Test query")

        assert result.success is True
        assert result.final_answer == "Answer without tool"

    def test_handle_finish_action(self, agent):
        """Test handling finish action"""
        action = AgentAction(reasoning="Done", action="finish", final_answer="Answer")

        step, should_finish = agent._handle_finish_action(action, iteration=1)

        assert should_finish is True
        assert step.action == "finish"
        assert step.tool_results[0].content == "Answer"

    @pytest.mark.asyncio
    async def test_handle_tool_calls(self, agent):
        """Test handling tool calls"""
        tool_call1 = ToolCall(tool_name="tool1", arguments="{}")
        tool_call2 = ToolCall(tool_name="tool2", arguments="{}")
        action = AgentAction(
            reasoning="Call tools",
            action="call_tool",
            tool_calls=[tool_call1, tool_call2],
        )

        mock_executor = Mock()
        mock_executor.execute_tool = AsyncMock(
            side_effect=[
                ToolResult(tool_name="tool1", success=True, content="Result1"),
                ToolResult(tool_name="tool2", success=True, content="Result2"),
            ]
        )
        agent.executor = mock_executor

        step, should_finish = await agent._handle_tool_calls(action, iteration=1)

        assert should_finish is False
        assert len(step.tool_calls) == 2
        assert len(step.tool_results) == 2
        assert mock_executor.execute_tool.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_tool_calls_no_tools(self, agent):
        """Test handling tool calls with no tools specified"""
        action = AgentAction(
            reasoning="Call tools but forgot to specify",
            action="call_tool",
            tool_calls=[],
        )

        step, should_finish = await agent._handle_tool_calls(action, iteration=1)

        assert should_finish is False
        assert len(step.tool_results) == 1
        assert "No tool calls specified" in step.tool_results[0].error

    def test_handle_unknown_action(self, agent):
        """Test handling unknown action"""
        action = AgentAction(reasoning="Test", action="call_tool")  # Will be modified
        action.action = "unknown_action"

        step, should_finish = agent._handle_unknown_action(action, iteration=1)

        assert should_finish is True
        assert "Unknown action" in step.tool_results[0].error

    def test_create_error_step(self, agent):
        """Test creating error step"""
        step = agent._create_error_step(iteration=1, error_msg="Test error")

        assert step.iteration == 1
        assert step.action == "finish"
        assert step.tool_results[0].error == "Test error"

    def test_format_tools(self, agent):
        """Test formatting tools list"""
        tools = [
            {
                "name": "search",
                "description": "Search tool",
                "inputSchema": {"properties": {"query": {"type": "string"}}},
            },
            {"name": "list", "description": "List tool"},
        ]

        formatted = agent._format_tools(tools)

        assert "search" in formatted
        assert "Search tool" in formatted
        assert "query" in formatted
        assert "list" in formatted

    def test_format_history(self, agent):
        """Test formatting execution history"""
        step1 = ExecutionStep(
            iteration=1,
            reasoning="First step",
            action="call_tool",
            tool_calls=[ToolCall(tool_name="tool1", arguments="{}")],
            tool_results=[ToolResult(tool_name="tool1", success=True, content="Result")],
        )
        step2 = ExecutionStep(
            iteration=2,
            reasoning="Second step",
            action="finish",
            tool_results=[ToolResult(tool_name="finish", success=True, content="Answer")],
        )

        formatted = agent._format_history([step1, step2])

        assert "Iteration 1" in formatted
        assert "First step" in formatted
        assert "tool1" in formatted
        assert "Iteration 2" in formatted
        assert "Second step" in formatted

    def test_format_history_empty(self, agent):
        """Test formatting empty history"""
        formatted = agent._format_history([])

        assert formatted == ""

    @pytest.mark.asyncio
    async def test_run_sync_wrapper(self, agent, mock_mcp_client, mock_model):
        """Test synchronous run wrapper"""
        # Mock available tools
        mock_executor = Mock()
        mock_executor.get_available_tools = AsyncMock(return_value=[])
        agent.executor = mock_executor

        action = AgentAction(reasoning="Done", action="finish", final_answer="Answer")
        mock_model.generate.return_value = action.model_dump()

        with patch("rhesis.sdk.services.mcp.agent.asyncio.run") as mock_run:
            mock_run.return_value = AgentResult(
                final_answer="Answer",
                execution_history=[],
                iterations_used=1,
                max_iterations_reached=False,
                success=True,
            )

            result = agent.run("Test query")

            assert result.success is True
            mock_run.assert_called_once()
